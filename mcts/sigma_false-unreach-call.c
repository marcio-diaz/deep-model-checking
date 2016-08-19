typedef int pthread_t;

int array[16];
int array_index=-1;
int sum = 0;
void *thread(void * arg)
{
  array[array_index] = 1;
  return 0;
}


int main()
{
  int tid;
  tid = 0;
  while (tid<16) {
    array_index++;
    pthread_create(&t[tid], 0, thread, 0);
    tid++;
  }
  tid = 0;
  while (tid<16) {
    pthread_join(t[tid], 0);
    tid++;
  }

  tid = 0;

  while (tid<16) {
    sum += array[tid];
    tid++;
  }
  assert(sum != 1);
  
  return 0;
}
