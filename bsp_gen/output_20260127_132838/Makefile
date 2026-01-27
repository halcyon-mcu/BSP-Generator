# Example Makefile for TI RM46 SCI driver
# Requires TI ARM CGT toolchain (armcl)

CC = armcl
CFLAGS = -mv7R4 --code_state=32 --float_support=VFPv3D16 -O2 -g
INCLUDES = -I.

SOURCES = sci.c sci_polling_example.c sci_interrupt_example.c sci_loopback_example.c
OBJECTS = $(SOURCES:.c=.obj)

all: $(OBJECTS)

%.obj: %.c
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

clean:
	rm -f *.obj

.PHONY: all clean
