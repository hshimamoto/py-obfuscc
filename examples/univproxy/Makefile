CC = gcc
LD = gcc
CFLAGS = -O2
LDFLAGS =

univproxy: univproxy.o
	$(LD) $(LDFLAGS) -o $@ univproxy.o

%.o: %.c
	$(CC) $(CFLAGS) -S -o $<.s $<
	$(OBFUS) $<.s
	$(CC) $(CFLAGS) -c -o $@ $<.s.obfus.s

clean:
	rm -f *.s *.o univproxy
