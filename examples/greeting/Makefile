CC = gcc
LD = gcc
CFLAGS = -O0 -fno-stack-protector -no-pie
LDFLAGS = -no-pie

greeting: greeting.o
	$(LD) $(LDFLAGS) -o $@ greeting.o

%.o: %.c
	$(CC) $(CFLAGS) -S -o $<.s $<
	$(OBFUS) $<.s
	$(CC) $(CFLAGS) -c -o $@ $<.s.obfus.s

clean:
	rm -f *.s *.o greeting
