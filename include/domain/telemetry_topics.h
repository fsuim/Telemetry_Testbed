#ifndef TELEMETRY_TOPICS_H
#define TELEMETRY_TOPICS_H

/* Fonte única para tópicos MQTT usados pelo simulador, gateway e ferramentas. */

#define TELEMETRY_TOPIC_STATE "/robot/v1/telemetry/state"

#define TELEMETRY_TOPIC_IMU_ACC  "/robot/sensors/imu0/acc"
#define TELEMETRY_TOPIC_IMU_GYRO "/robot/sensors/imu0/gyro"

#define TELEMETRY_TOPIC_TILT "/robot/sensors/tilt0/tilt"

#define TELEMETRY_TOPIC_MOTOR1_TICS "/robot/sensors/motor1/tics"
#define TELEMETRY_TOPIC_MOTOR1_RPM  "/robot/sensors/motor1/rpm"
#define TELEMETRY_TOPIC_MOTOR1_TEMP "/robot/sensors/motor1/temperature"
#define TELEMETRY_TOPIC_MOTOR1_VPS  "/robot/sensors/motor1/voltage_power_stage"
#define TELEMETRY_TOPIC_MOTOR1_CPS  "/robot/sensors/motor1/current_power_stage"

#define TELEMETRY_TOPIC_MOTOR2_TICS "/robot/sensors/motor2/tics"
#define TELEMETRY_TOPIC_MOTOR2_RPM  "/robot/sensors/motor2/rpm"
#define TELEMETRY_TOPIC_MOTOR2_TEMP "/robot/sensors/motor2/temperature"
#define TELEMETRY_TOPIC_MOTOR2_VPS  "/robot/sensors/motor2/voltage_power_stage"
#define TELEMETRY_TOPIC_MOTOR2_CPS  "/robot/sensors/motor2/current_power_stage"

#endif /* TELEMETRY_TOPICS_H */
