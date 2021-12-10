OBFUS = $(PWD)/obfus-trans.py
export OBFUS

all:
	$(MAKE) -C examples

clean:
	$(MAKE) -C examples clean
