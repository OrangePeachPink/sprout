# lib

Project-private libraries live here, each in its own subfolder (for example
`lib/MoistureSensor/` containing `MoistureSensor.h` and `MoistureSensor.cpp`).

PlatformIO compiles and links anything in this folder automatically. External or
published libraries are declared in `platformio.ini` under `lib_deps` instead.
