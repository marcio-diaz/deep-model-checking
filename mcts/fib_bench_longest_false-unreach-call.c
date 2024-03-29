extern void __VERIFIER_error() __attribute__ ((__noreturn__));

#include <pthread.h>

void __VERIFIER_assert(int expression) { if (!expression) { ERROR: __VERIFIER_error();}; return; }

int i=1, j=1;

#define NUM 21

void *
t1(void* arg)
{
  int k = 0;
  
  while (k < NUM) {
    i+=j;
    k++;
  }
  pthread_exit(NULL);
}

void *
t2(void* arg)
{
  int k = 0;
  
  while (k < NUM) {
    j += i;
    k++;
  }

  pthread_exit(NULL);
}

int
main(int argc, char **argv)
{
  pthread_t id1, id2;

  pthread_create(&id1, NULL, t1, NULL);
  pthread_create(&id2, NULL, t2, NULL);

  assert(i < 701408733 && j < 701408733); 

  return 0;
}
