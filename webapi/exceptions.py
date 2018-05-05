"""WebAPI defined exceptions"""

from collections import Iterable


class WebAPIError(Exception):
    """Base class for any api error"""
    pass


class ConfigError(Exception):
    """Base class for any configuration error"""
    pass


class ConfigOptionTypeError(ConfigError):
    """Configuration value cannot cast to the desired value"""
    template = "Wrong type for option \"{}\" in \"{}\" block. " \
               "Type must be {} but current type is {}."
    def __init__(self, option, block, wanted_types, actual_type):
        if isinstance(wanted_types, Iterable):
            wanted_types = "one of {%s}" % ", ".join(map(str, wanted_types))
        super().__init__(self.template.format(
            option, block, wanted_types, actual_type))


class ConfigUnknownOptionError(ConfigError):
    """Configuration field doesn't match any option"""
    template = "Option \"{}\" in block \"{}\" is unknown."
    def __init__(self, option, block):
        super().__init__(self.template.format(option, block))


class ConfigMissingOptionError(ConfigError):
    """Configuration field is missing"""
    template = "Options {{{}}} from block \"{}\" are missing."
    def __init__(self, missings, block):
        super().__init__(self.template.format(", ".join(missings), block))

class GroupError(WebAPIError):
    pass

class GroupExists(GroupError):
    pass

class GroupDoesntExist(GroupError):
    pass

class PlayerInGroupAlready(GroupError):
    pass

class PlayerNotInGroup(GroupError):
    pass

class GroupInQueueAlready(GroupError):
    pass

class GroupIsFull(GroupError):
    pass

class GroupPlayingAlready(GroupError):
    pass