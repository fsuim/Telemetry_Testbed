CC ?= gcc

BUILD_DIR ?= build
OUT_SIM ?= robot_sim
OUT_GW ?= telemetry_gateway
OUT_DUMP ?= state_dump

CPPFLAGS += -Iinclude \
            -Iinclude/app \
            -Iinclude/domain \
            -Iinclude/infra \
            -Iinclude/sim \
            -Iinclude/util \
            -Iinclude/sim/sensors \
            -Igenerated/protobuf-c

CFLAGS ?= -O2 -Wall -Wextra -std=c11 -pthread
CFLAGS += -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE

LIB_COMMON := -lm -pthread -lrt
LIB_MQTT := -lmosquitto
LIB_PB := -lprotobuf-c
LIB_SQLITE := -lsqlite3

PROTO_SRC := proto/robot_telemetry.proto
PB_C := generated/protobuf-c/robot_telemetry.pb-c.c
PB_H := generated/protobuf-c/robot_telemetry.pb-c.h

ROBOT_SRC := \
    src/apps/robot_main.c \
    src/infra/mqtt/mqtt_client.c \
    src/sim/sensors/imu_sensor.c \
    src/sim/sensors/tilt_sensor.c \
    src/sim/sensors/motor1_sensor.c \
    src/sim/sensors/motor2_sensor.c \
    src/sim/telemetry_cache.c \
    src/sim/telemetry_state_pub.c \
    $(PB_C)

GW_SRC := \
    src/apps/telemetry_gateway_main.c \
    src/app/telemetry_gateway.c \
    src/infra/websocket/ws_server.c \
    src/infra/persistence/db_sqlite.c \
    src/infra/mqtt/mqtt_client.c \
    $(PB_C)

DUMP_SRC := \
    src/apps/state_dump.c \
    $(PB_C)

all: $(OUT_SIM) $(OUT_GW) $(OUT_DUMP)

$(OUT_SIM): $(ROBOT_SRC)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(ROBOT_SRC) -o $@ $(LIB_MQTT) $(LIB_PB) $(LIB_COMMON)

$(OUT_GW): $(GW_SRC)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(GW_SRC) -o $@ $(LIB_MQTT) $(LIB_PB) $(LIB_SQLITE) $(LIB_COMMON)

$(OUT_DUMP): $(DUMP_SRC)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DUMP_SRC) -o $@ $(LIB_MQTT) $(LIB_PB) $(LIB_COMMON)

.PHONY: all clean distclean proto check smoke-test

proto: $(PB_C) $(PB_H)

$(PB_C) $(PB_H): $(PROTO_SRC)
	mkdir -p generated/protobuf-c
	protoc-c --c_out=generated/protobuf-c -Iproto $(PROTO_SRC)

check:
	$(CC) $(CPPFLAGS) $(CFLAGS) -fsyntax-only $(ROBOT_SRC) $(GW_SRC) $(DUMP_SRC)

smoke-test: all
	bash scripts/dev/smoke_test.sh

clean:
	rm -f $(OUT_SIM) $(OUT_GW) $(OUT_DUMP)
	rm -rf $(BUILD_DIR)
	rm -f *.o src/**/*.o generated/**/*.o

distclean: clean
	rm -f telemetry.db telemetry.db-wal telemetry.db-shm
