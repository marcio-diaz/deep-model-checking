//typedef int pthread_t;

#include <pthread.h>
#include <assert.h>

int array[11];
int array_index=-1;
int sum = 0;
int t[11];

void *thread(void * arg)
{
  array[array_index] = 1;
  return 0;
}


int main()
{
  int tid;
  tid = 0;
  while (tid<11) {
    array_index++;
    pthread_create(&t[tid], 0, thread, 0);
    tid++;
  }
  tid = 0;
  while (tid<11) {
    pthread_join(t[tid], 0);
    tid++;
  }

  tid = 0;

  while (tid<11) {
    sum += array[tid];
    tid++;
  }
  assert(sum != 1);
  
  return 0;
}
