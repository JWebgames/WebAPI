class ConfigError(Exception):
    pass

class ConfigOptionTypeError(ConfigError):
    template = "Wrong value type for option \"{}\" in \"{}\" block. " \
               "Type must be {}, current type is {}."
    def __init__(self, option, block, actual_type):
        super().__init__(self, self.template.format(
            option, block, block._field_types[option], actual_type))


class ConfigUnknownOption(ConfigError):
    template = "Option \"{}\" in block \"{}\" is unknown."
    def __init__(self, option, block):
        super().__init__(self, self.template.format(
            option, block))
