#include <stdio.h>

void hello(void)
{
	printf("Hello");
}

void world(void)
{
	printf("World");
}

int main(int argc, char **argv)
{
	hello();
	printf(", ");
	world();
	printf("\n");

	return 0;
}
