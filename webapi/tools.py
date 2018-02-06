from typing import Union, Optional


def cast(typ, val):
    return real_type(typ)(val)


def real_type(typ):
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    else:
        return typ
