#ifndef TILT_SENSOR_H
#define TILT_SENSOR_H

#include <pthread.h>
#include "sim/sensor_runtime.h"
#include "sim/telemetry_cache.h"

int tilt_sensor_start(const sensor_runtime_t *rt, telemetry_cache_t *cache, pthread_t *out_thread);

#endif