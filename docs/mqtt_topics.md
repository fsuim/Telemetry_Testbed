# MQTT Topics

The single source of truth in the code is `include/domain/telemetry_topics.h`.

## Protobuf snapshot

| Topic | Payload | Producer | Consumer |
|---|---|---|---|
| `/robot/v1/telemetry/state` | `robot.v1.TelemetryState` Protobuf | `robot_sim` | `telemetry_gateway`, `state_dump` |

## RAW sensors

| Topic | Payload | Producer |
|---|---|---|
| `/robot/sensors/imu0/acc` | little-endian binary | IMU |
| `/robot/sensors/imu0/gyro` | little-endian binary | IMU |
| `/robot/sensors/tilt0/tilt` | little-endian binary | Tilt |
| `/robot/sensors/motor1/tics` | little-endian binary | Motor 1 |
| `/robot/sensors/motor1/rpm` | little-endian binary | Motor 1 |
| `/robot/sensors/motor1/temperature` | little-endian binary | Motor 1 |
| `/robot/sensors/motor1/voltage_power_stage` | little-endian binary | Motor 1 |
| `/robot/sensors/motor1/current_power_stage` | little-endian binary | Motor 1 |
| `/robot/sensors/motor2/tics` | little-endian binary | Motor 2 |
| `/robot/sensors/motor2/rpm` | little-endian binary | Motor 2 |
| `/robot/sensors/motor2/temperature` | little-endian binary | Motor 2 |
| `/robot/sensors/motor2/voltage_power_stage` | little-endian binary | Motor 2 |
| `/robot/sensors/motor2/current_power_stage` | little-endian binary | Motor 2 |
