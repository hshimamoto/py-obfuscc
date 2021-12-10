CC = gcc
LD = gcc
CFLAGS = -O2
LDFLAGS =

helloworld: helloworld.o
	$(LD) $(LDFLAGS) -o $@ helloworld.o

%.o: %.c
	$(CC) $(CFLAGS) -S -o $<.s $<
	$(OBFUS) $<.s
	$(CC) $(CFLAGS) -c -o $@ $<.s.obfus.s

clean:
	rm -f *.s *.o helloworld
