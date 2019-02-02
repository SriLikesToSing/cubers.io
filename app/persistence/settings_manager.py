""" Utility module for persisting and retrieving user settings. """

from collections import namedtuple

from app import DB
from app.persistence.models import UserSetting

# -------------------------------------------------------------------------------------------------

# Constants which correspond to a `setting_code` in the UserSettings database table
# pylint: disable=R0903,C0111
class SettingCode():
    USE_INSPECTION_TIME    = 'use_inspection_time'
    HIDE_INSPECTION_TIME   = 'hide_inspection_time'
    HIDE_RUNNING_TIMER     = 'hide_running_timer'
    REDDIT_COMP_NOTIFY     = 'reddit_comp_notify'
    DEFAULT_TO_MANUAL_TIME = 'manual_time_entry_by_default'

    # Custom cube colors
    USE_CUSTOM_CUBE_COLORS = 'use_custom_cube_colors'
    CUSTOM_CUBE_COLOR_U    = 'custom_cube_color_U'
    CUSTOM_CUBE_COLOR_F    = 'custom_cube_color_F'
    CUSTOM_CUBE_COLOR_R    = 'custom_cube_color_R'
    CUSTOM_CUBE_COLOR_D    = 'custom_cube_color_D'
    CUSTOM_CUBE_COLOR_B    = 'custom_cube_color_B'
    CUSTOM_CUBE_COLOR_L    = 'custom_cube_color_L'

# Denotes the type of setting, aka boolean, free-form text, etc
class SettingType():
    BOOLEAN   = 'boolean'
    HEX_COLOR = 'hex_color'  # hex color code aka "#FFC1D2"

# Encapsulates necessary information about each setting
class SettingInfo():
    def __init__(self, title, validator, setting_type, default_value, affects=None):
        self.title = title
        self.validator = validator
        self.setting_type = setting_type
        self.default_value = default_value
        self.affects = affects # an optional list of SettingCodes that this code enables/disables

# -------------------------------------------------------------------------------------------------

TRUE_STR  = 'true'
FALSE_STR = 'false'

def boolean_validator(value):
    """ Validates a boolean setting value as text. """
    if value is None:
        return FALSE_STR
    if value in [True, False]:
        return str(value).lower()
    if value in [TRUE_STR, FALSE_STR]:
        return value
    raise ValueError("{} is not an acceptable value.".format(value))


HEX_CHARACTERS = set([c for c in 'ABCDEF0123456789'])

def hex_color_validator(value):
    """ Validates a string which represents a color in hex format. """

    if value[0] != "#":
        raise ValueError("{} is not a hex color value. It does not start with '#'.".format(value))

    for char in value[1:]:
        if char not in HEX_CHARACTERS:
            msg = "{} is not a hex color value. {} is not hexadecimal.".format(value, char)
            raise ValueError(msg)

    return value


# -------------------------------------------------------------------------------------------------

SETTING_INFO_MAP = {
    SettingCode.USE_INSPECTION_TIME : SettingInfo(
        title         = "Use WCA 15s Inspection Time",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR,
        affects       = [SettingCode.HIDE_INSPECTION_TIME]
    ),

    SettingCode.HIDE_INSPECTION_TIME : SettingInfo(
        title         = "Hide Inspection Time Countdown",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR
    ),

    SettingCode.HIDE_RUNNING_TIMER : SettingInfo(
        title         = "Hide Timer While Running",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR
    ),

    SettingCode.REDDIT_COMP_NOTIFY : SettingInfo(
        title         = "Receive New Competition Reddit Notification",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR
    ),

    SettingCode.DEFAULT_TO_MANUAL_TIME : SettingInfo(
        title         = "Use Manual Time Entry",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR
    ),

    SettingCode.USE_CUSTOM_CUBE_COLORS : SettingInfo(
        title         = "Use Custom Cube Colors",
        validator     = boolean_validator,
        setting_type  = SettingType.BOOLEAN,
        default_value = FALSE_STR,
        affects       = [SettingCode.CUSTOM_CUBE_COLOR_B, SettingCode.CUSTOM_CUBE_COLOR_D,
                         SettingCode.CUSTOM_CUBE_COLOR_F, SettingCode.CUSTOM_CUBE_COLOR_L,
                         SettingCode.CUSTOM_CUBE_COLOR_R, SettingCode.CUSTOM_CUBE_COLOR_U]
    ),

    SettingCode.CUSTOM_CUBE_COLOR_U : SettingInfo(
        title         = "Color for U",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#FFFFFF"
    ),

    SettingCode.CUSTOM_CUBE_COLOR_F : SettingInfo(
        title         = "Color for F",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#00FF00"
    ),

    SettingCode.CUSTOM_CUBE_COLOR_R : SettingInfo(
        title         = "Color for R",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#FF0000"
    ),

    SettingCode.CUSTOM_CUBE_COLOR_D : SettingInfo(
        title         = "Color for D",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#FFFF00"
    ),

    SettingCode.CUSTOM_CUBE_COLOR_B : SettingInfo(
        title         = "Color for B",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#0000FF"
    ),

    SettingCode.CUSTOM_CUBE_COLOR_L : SettingInfo(
        title         = "Color for L",
        validator     = hex_color_validator,
        setting_type  = SettingType.HEX_COLOR,
        default_value = "#FF8800"
    ),
}

SettingsEditTuple = namedtuple('SettingsEditTuple', ['code', 'title', 'value', 'type', 'affects'])

# -------------------------------------------------------------------------------------------------

def __create_unset_setting(user_id, setting_code):
    """ Creates a UserSetting for the specified user and setting code, with a default value. """

    if setting_code not in SETTING_INFO_MAP.keys():
        raise ValueError("That setting doesn't exist!")

    setting_info = SETTING_INFO_MAP[setting_code]
    user_setting  = UserSetting(user_id=user_id, setting_code=setting_code,\
        setting_value=setting_info.default_value)

    DB.session.add(user_setting)
    DB.session.commit()

    return user_setting


def get_default_value_for_setting(setting_code):
    """ Retrieves a default value for a particular setting code. """

    if setting_code not in SETTING_INFO_MAP.keys():
        raise ValueError("That setting doesn't exist!")

    return SETTING_INFO_MAP[setting_code].default_value


def get_setting_for_user(user_id, setting_code):
    """ Retrieves a user's setting for a given setting code. """

    setting = DB.session.\
        query(UserSetting).\
        filter(UserSetting.user_id == user_id).\
        filter(UserSetting.setting_code == setting_code).\
        first()

    return setting.setting_value if setting \
        else __create_unset_setting(user_id, setting_code).setting_value


def get_settings_for_user_for_edit(user_id, setting_codes):
    """ Retrieves the settings specified in a data format suitable to passing to the front-end
    for editing and viewing. """

    # Retrieve the settings for the specified user and all setting codes provided
    settings = DB.session.\
        query(UserSetting).\
        filter(UserSetting.user_id == user_id).\
        filter(UserSetting.setting_code.in_(setting_codes)).\
        all()

    # If the number of retrieved settings != the number of codes provided, one or more settings
    # haven't been initialized for this user. Do a dummy retrieval of all the codes provided to
    # to ensure all settings have been initialized, then call this function again and return
    # all the settings
    if len(settings) < len(setting_codes):
        for code in setting_codes:
            get_setting_for_user(user_id, code)
        return get_settings_for_user_for_edit(user_id, setting_codes)


    # I know this is terrible in general (O(n^2)), but it's fine for small numbers of settings,
    # and I don't want to implement a real sort key lambda for this right now
    ordered_settings = list()
    for code in setting_codes:
        for setting in settings:
            if setting.setting_code == code:
                ordered_settings.append(setting)
                break

    return [
        SettingsEditTuple(
            code     = setting.setting_code,
            value    = setting.setting_value,
            title    = SETTING_INFO_MAP[setting.setting_code].title,
            affects  = SETTING_INFO_MAP[setting.setting_code].affects,
            type     = SETTING_INFO_MAP[setting.setting_code].setting_type
        )
        for setting in ordered_settings
    ]


def set_setting_for_user(user_id, setting_code, setting_value):
    """ Sets a user's setting for a given setting code. """

    if setting_code not in SETTING_INFO_MAP.keys():
        raise ValueError("That setting doesn't exist!")

    setting_info = SETTING_INFO_MAP[setting_code]
    setting_value = setting_info.validator(setting_value)

    setting = DB.session.\
        query(UserSetting).\
        filter(UserSetting.user_id == user_id).\
        filter(UserSetting.setting_code == setting_code).\
        first()

    if not setting:
        setting = __create_unset_setting(user_id, setting_code)

    setting.setting_value = setting_value
    DB.session.add(setting)
    DB.session.commit()

    return setting
