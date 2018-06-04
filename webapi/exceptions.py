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

class NotFoundError(WebAPIError):
    pass

class GroupError(WebAPIError):
    pass

class GameDoesntExist(GroupError):
    pass

class GroupDoesntExist(GroupError):
    pass

class PlayerInGroupAlready(GroupError):
    pass

class PlayerNotInGroup(GroupError):
    pass

class PlayerNotInParty(GroupError):
    pass

class GroupIsFull(GroupError):
    pass

class GroupNotReady(GroupError):
    pass

class WrongGroupState(GroupError):
    def __init__(self, current, wanted):
        if isinstance(wanted, Iterable):
            super().__init__(self, "Current: {}. Require: {{{}}}".format(
                current.name, ", ".join([w.name for w in wanted])
            ))
        else:
            super().__init__(self, "Current: {}. Require: {}".format(
                current.name, wanted.name
            ))

class PartyDoesntExist(GroupError):
    pass
