#include <stdio.h>

void greeting(const char *name)
{
	printf("Hello, %s\n", name);
}

int main(int argc, char **argv)
{
	char name[32];

	printf("Name?");
	fgets(name, 256, stdin);
	greeting(name);

	return 0;
}
