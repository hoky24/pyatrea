from enum import IntEnum

REQUEST_TIMEOUT = 15  # seconds


class AtreaProgram(IntEnum):
    MANUAL = 0
    WEEKLY = 1
    TEMPORARY = 2


class AtreaMode(IntEnum):
    OFF = 0
    AUTOMATIC = 1
    VENTILATION = 2
    CIRCULATION_AND_VENTILATION = 3
    CIRCULATION = 4
    NIGHT_PRECOOLING = 5
    DISBALANCE = 6
    OVERPRESSURE = 7
    PERIODIC_VENTILATION = 8
    STARTUP = 9
    RUNDOWN = 10
    DEFROSTING = 11
    EXTERNAL = 12
    HP_DEFROSTING = 13
    IN1 = 14
    IN2 = 15
    D1 = 16
    D2 = 17
    D3 = 18
    D4 = 19
