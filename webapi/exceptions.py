class ConfigError(Exception):
    pass

class ConfigOptionTypeError(ConfigError):
    template = "Wrong value type for option \"{}\" in \"{}\" block. " \
               "Type must be {}, current type is {}."
    def __init__(self, option, block, actual_type):
        super().__init__(self.template.format(
            option, block, block._field_types[option], actual_type))


class ConfigUnknownOptionError(ConfigError):
    template = "Option \"{}\" in block \"{}\" is unknown."
    def __init__(self, option, block):
        super().__init__(self.template.format(option, block))

class ConfigMissingOptionError(ConfigError):
    template = "Options {{{}}} from block \"{}\" are missing."
    def __init__(self, missings, block):
        super().__init__(self.template.format(", ".join(missings), block))