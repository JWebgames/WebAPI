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
    """Ressource not found"""
    pass

class GroupError(WebAPIError):
    """Base exception for any group error"""
    pass

class GameDoesntExist(GroupError):
    """The specified game doesn't exist"""
    pass

class GroupDoesntExist(GroupError):
    """The specified group doesn't exist"""
    pass

class PlayerInGroupAlready(GroupError):
    """The player tried to join a group while beeing in a group"""
    pass

class PlayerNotInGroup(GroupError):
    """
    The player tried an action that require him to be part
    of a group but he is not
    """
    pass

class PlayerNotInParty(GroupError):
    """
    The player tried an action that require his group to be in
    InParty state but is not
    """
    pass

class GroupIsFull(GroupError):
    """The player tried to join a filled group"""
    pass

class GroupNotReady(GroupError):
    """
    The player tried an action that require the all group
    to be ready but is not
    """
    pass

class WrongGroupState(GroupError):
    """
    The player tried an action that is invalid for the current
    state of his group
    """
    def __init__(self, current, wanted):
        """Just a pretty format"""
        if isinstance(wanted, Iterable):
            super().__init__(self, "Current: {}. Require: {{{}}}".format(
                current.name, ", ".join([w.name for w in wanted])
            ))
        else:
            super().__init__(self, "Current: {}. Require: {}".format(
                current.name, wanted.name
            ))

class PartyDoesntExist(GroupError):
    """
    The player tried an action that require him to be playing
    but he is not
    """
    pass
