(function() {
    var app = window.app;

    // The events that EventsDataManager can emit
    var EVENT_SET_COMPLETE = "event_set_complete";
    var EVENT_SET_NO_STATUS = 'event_set_no_status';
    var EVENT_SET_INCOMPLETE = "event_set_incomplete";
    var EVENT_SUMMARY_CHANGE = "event_summary_change";
    var EVENT_SOLVE_RECORD_UPDATED = "event_solve_record_updated";

    /**
     * Manages the state of the solve cards
     */
    function EventsDataManager() {
        app.EventEmitter.call(this);

        this.events_data = app.events_data;
        this.comp_id = app.comp_id;

        this._setCorrectScrambleStatus();
        this._registerTimerEventHandlers();
    }
    EventsDataManager.prototype = Object.create(app.EventEmitter.prototype);

    /**
     * On page load, build all the summaries for the incomplete events, since they don't
     * come with the event data from the server.
     */
    EventsDataManager.prototype.buildAllIncompleteSummaries = function() {
        $.each(this.events_data, function(id, event) {
            if (event.status == 'incomplete') { this._recordIncompleteSummaryForEvent(event); }
        }.bind(this));
    };

    /**
     * Iterate over all the solves for this event, and updates data about the event itself based
     * on the results
     */
    EventsDataManager.prototype._updateSingleEventStatus = function(event) {
        // Count the total number of solves and the number of completed solves
        var total_solves = event.scrambles.length;
        event.num_completed_solves = 0;
        $.each(event.scrambles, function(i, scramble){
            if (Boolean(scramble.time)) { event.num_completed_solves += 1; }
        });

        // Since we're updating this event, set the "blind status" flag to incomplete
        // until the after we save the event to the server and all 3 solves are done.
        // This ensures that the timer screen shows the best solve at all times, from
        // the most recently calculated event results, not stale data
        if (event.event_format == 'Bo3') { event.blind_status = 'incomplete'; }

        // If total solves == completed solves, or in a Bo3 event at least 1 solve is complete, the event is complete.
        // Grab a times summary from the server for the complete event
        // and emit an event so the card is visually updated.
        if (total_solves == event.num_completed_solves || (event.event_format == 'Bo3' && event.num_completed_solves > 0)) {
            event.status = 'complete';
            this._saveEvent(event);
            this.emit(EVENT_SET_COMPLETE, event.comp_event_id);
            return;
        }

        // If the event has some completed solves, but not all, it's incomplete.
        // Build a partial summary for the incomplete event and emit an event
        // so the card is visually updated.
        if (event.num_completed_solves > 0) {
            event.status = 'incomplete';
            this._saveEvent(event);
            this._recordIncompleteSummaryForEvent(event);
            this.emit(EVENT_SET_INCOMPLETE, event.comp_event_id);
            this.emit(EVENT_SUMMARY_CHANGE, event.comp_event_id);
            return;
        }
        
        // There are no solves complete for this event, make sure the status and summary
        // are null and the card has no visual indicator
        event.status = null;
        event.summary = null;
        this._saveEvent(event);
        this.emit(EVENT_SET_NO_STATUS, event.comp_event_id);
        this.emit(EVENT_SUMMARY_CHANGE, event.comp_event_id);
    };

    /**
     * Saves the event so the user doesn't lose solves if they navigate away.
     */
    EventsDataManager.prototype._saveEvent = function(event) {
        if (app.user_logged_in) {
            this._saveEventToServer(event);
        } else {
            // this._saveEventToLocalStorage(event);
        }
    };

    /**
     * Makes a call out to the server to save the event to the database
     */
    EventsDataManager.prototype._saveEventToServer = function(event) {
        // wrap event in an object where the property name is the comp event id,
        // and the property value is the event itself. This is just so server-side
        // logic can be re-used
        var event_data = {};
        event_data[event.comp_event_id] = event;

        var onSaveCompleteRecordSummary = function(data, event) {
            if (event.status != 'complete') {
                return;
            }

            // Record a separate "blind status" flag for use when deciding whether to
            // display the user's results in the scramble area. We only want to show the
            // result after calling save to the server, and all solves are completed, so
            // we're confident we're showing the actual best solve and not just the best of
            // the first 2 solves
            if (event.event_format == 'Bo3' && event.num_completed_solves == 3) {
                event.blind_status = 'complete';
            }

            // If the event is complete, record useful summary information about the results
            // so we can use that to display stuff in various places
            data = JSON.parse(data);
            event.result       = data.result;
            event.summary      = data.summary;
            event.single       = data.single;
            event.average      = data.average;
            event.wasPbSingle  = data.wasPbSingle;
            event.wasPbAverage = data.wasPbAverage;

            this.emit(EVENT_SUMMARY_CHANGE, event.comp_event_id);
        }.bind(this);

        $.ajax({
            url: "/save_event",
            type: "POST",
            data: JSON.stringify(event_data),
            contentType: "application/json",
            success: function (data) { onSaveCompleteRecordSummary(data, event); },
        });
    };

    /**
     * Saves an "in-progress" summary for this event
     * Ex: ? = solve1, solve2, ...
     */
    EventsDataManager.prototype._recordIncompleteSummaryForEvent = function(event) {
        var time_strings = [];
        $.each(event.scrambles, function(i, scramble) {
            if (!scramble.time) { return true; }
            var timeStr = "DNF";
            if (!scramble.isDNF) {
                timeStr = app.convertRawCsForSolveCard(scramble.time, scramble.isPlusTwo);
                if (scramble.isPlusTwo) { timeStr += '+'; }
            }
            time_strings.push(timeStr);
        });
        event.summary = "? = " + time_strings.join(", ");
    };

    /**
     * Checks each scramble on load to see if a time is set. If yes, set status to complete,
     * otherwise set status to incomplete.
     */
    EventsDataManager.prototype._setCorrectScrambleStatus = function() {
        $.each(this.events_data, function(i, comp_event) {
            $.each(comp_event.scrambles, function(j, scramble) {
                scramble.status = Boolean(scramble.time) ? 'complete' : 'incomplete';
            });
        });
    };

    /**
     * Gets the next incomplete scramble for the provided competition event ID
     */
    EventsDataManager.prototype.getNextIncompleteScramble = function(comp_event_id) {
        var nextScramble = null;
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.status != 'complete') {
                nextScramble = curr_solve_record;
                return false;
            }
        });
        return nextScramble;
    };

    /**
     * Returns the current competition id.
     */
    EventsDataManager.prototype.getCompId = function() {
        return this.comp_id;
    };

    /**
     * Returns all of the events data.
     */
    EventsDataManager.prototype.getEventsData = function() {
        return this.events_data;
    };

    /**
     * Returns the event name for the given comp event id.
     */
    EventsDataManager.prototype.getEventName = function(comp_event_id) {
        return this.events_data[comp_event_id].name;
    };

    /**
     * Returns the event data for the given comp event id.
     */
    EventsDataManager.prototype.getDataForEvent = function(comp_event_id) {
        return this.events_data[comp_event_id];
    };

    /**
     * Clears penalties for the specified comp event and scramble ID
     */
    EventsDataManager.prototype.clearPenalty = function(comp_event_id, scramble_id) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.isDNF     = false;
            curr_solve_record.isPlusTwo = false;
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Sets DNF for the specified comp event and scramble ID
     */
    EventsDataManager.prototype.setDNF = function(comp_event_id, scramble_id) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.isDNF     = true;
            curr_solve_record.isPlusTwo = false;
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Deletes the solve time for the specified comp event and scramble ID
     */
    EventsDataManager.prototype.deleteSolveTime = function(comp_event_id, scramble_id) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.time   = null;
            curr_solve_record.status = null;
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);

        var data = {};
        data.scramble_id = scramble_id;
        data.friendly_time_full = '—';
        data.is_delete = true;
        data.comp_event_id = comp_event_id;

        this.emit(EVENT_SOLVE_RECORD_UPDATED, data);
    };

    /**
     * Sets plus two for the specified comp event and scramble ID
     */
    EventsDataManager.prototype.setPlusTwo = function(comp_event_id, scramble_id) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.isDNF     = false;
            curr_solve_record.isPlusTwo = true;
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Sets the solve time (in centiseconds) for the specified comp event and scramble ID
     */
    EventsDataManager.prototype.setSolveTimeForManualEntry = function(comp_event_id, scramble_id, cs) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.isDNF     = false;
            curr_solve_record.isPlusTwo = false;
            curr_solve_record.time      = cs;
            curr_solve_record.status    = "complete";
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);

        var data = {};
        data.scramble_id = scramble_id;
        data.friendly_time_full = app.convertRawCsForSolveCard(cs, false);
        data.comp_event_id = comp_event_id;
        this.emit(EVENT_SOLVE_RECORD_UPDATED, data);
    };

    /**
     * Returns the solve record for specified comp event and scramble ID
     */
    EventsDataManager.prototype.getSolveRecord = function(comp_event_id, scramble_id) {
        var solveRecord = null;
        $.each(this.events_data[comp_event_id].scrambles, function(i, currSolveRecord) {
            if (currSolveRecord.id != scramble_id) { return true; }
            solveRecord = currSolveRecord;
            return false;
        });
        return solveRecord;
    };

    /**
     * Sets the FMC solve length (as "centi-moves", so the Mo3 logic works without additional hacks)
     */
    EventsDataManager.prototype.setFMCSolveLength = function(comp_event_id, scramble_id, length) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, currSolveRecord) {
            if (currSolveRecord.id != scramble_id) { return true; }
            currSolveRecord.time   = (length * 100);
            currSolveRecord.status = "complete";
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Unsets the FMC solve so there's no recorded solve length
     */
    EventsDataManager.prototype.unsetFMCSolve = function(comp_event_id, scramble_id) {
        $.each(this.events_data[comp_event_id].scrambles, function(i, currSolveRecord) {
            if (currSolveRecord.id != scramble_id) { return true; }
            currSolveRecord.time = null;
            currSolveRecord.status = null;
            return false;
        });
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Sets the comment for the specified competition event.
     */
    EventsDataManager.prototype.setCommentForEvent = function(comment, comp_event_id) {
        this.events_data[comp_event_id].comment = comment;
        this._updateSingleEventStatus(this.events_data[comp_event_id]);
    };

    /**
     * Updates a solve in the events data with the elapsed time from the 
     */
    EventsDataManager.prototype._updateSolveFromTimerData = function(timerStopData) {

        var comp_event_id = timerStopData.comp_event_id;
        var scramble_id  = timerStopData.scramble_id;

        $.each(this.events_data[comp_event_id].scrambles, function(i, curr_solve_record) {
            if (curr_solve_record.id != scramble_id) { return true; }
            curr_solve_record.time      = timerStopData.rawTimeCs;
            curr_solve_record.isDNF     = timerStopData.isDNF;
            curr_solve_record.isPlusTwo = timerStopData.isPlusTwo;
            curr_solve_record.status    = "complete";
            return false;
        });

        this._updateSingleEventStatus(this.events_data[comp_event_id]);
        this.emit(EVENT_SOLVE_RECORD_UPDATED, timerStopData);
    };

    /**
     * Register handlers for timer events.
     */
    EventsDataManager.prototype._registerTimerEventHandlers = function() {
        app.timer.on(app.EVENT_TIMER_STOP, this._updateSolveFromTimerData.bind(this));
    };
  
    // Make EventsDataManager and event names visible at app scope
    app.EventsDataManager = EventsDataManager;
    app.EVENT_SOLVE_RECORD_UPDATED = EVENT_SOLVE_RECORD_UPDATED;
    app.EVENT_SET_COMPLETE = EVENT_SET_COMPLETE;
    app.EVENT_SET_NO_STATUS = EVENT_SET_NO_STATUS;
    app.EVENT_SUMMARY_CHANGE = EVENT_SUMMARY_CHANGE;
    app.EVENT_SET_INCOMPLETE = EVENT_SET_INCOMPLETE;
})();