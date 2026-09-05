CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -std=c11
CPPFLAGS += $(shell pkg-config --cflags libnfc)
LDLIBS += $(shell pkg-config --libs libnfc)

.PHONY: all clean

all: leitor_pn532

leitor_pn532: leitor_pn532.c
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDLIBS)

clean:
	$(RM) leitor_pn532

