from collections import Iterable

class ConfigError(Exception):
    pass

class ConfigOptionTypeError(ConfigError):
    template = "Wrong type for option \"{}\" in \"{}\" block. " \
               "Type must be {} but current type is {}."
    def __init__(self, option, block, wanted_types, actual_type):
        if isinstance(wanted_types, Iterable):
            wanted_types = "one of {%s}" % ", ".join(map(str, wanted_types))
        super().__init__(self.template.format(
            option, block, wanted_types, actual_type))


class ConfigUnknownOptionError(ConfigError):
    template = "Option \"{}\" in block \"{}\" is unknown."
    def __init__(self, option, block):
        super().__init__(self.template.format(option, block))

class ConfigMissingOptionError(ConfigError):
    template = "Options {{{}}} from block \"{}\" are missing."
    def __init__(self, missings, block):
        super().__init__(self.template.format(", ".join(missings), block))
