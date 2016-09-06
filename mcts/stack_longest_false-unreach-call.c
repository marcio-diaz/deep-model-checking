extern void __VERIFIER_error() __attribute__ ((__noreturn__));
#include <pthread.h>
#include <stdio.h>

#define TRUE	  (1)
#define FALSE	  (0) 
#define SIZE	  (8)
#define OVERFLOW  (-1)
#define UNDERFLOW (-2)

unsigned int __VERIFIER_nondet_uint();
static int top=0;
static unsigned int arr[SIZE];
pthread_mutex_t m = 0;
_Bool flag=FALSE;

void error(void) 
{ 
  ERROR: __VERIFIER_error();  return;
}

void inc_top(void)
{
  top++;
  return;
}

void dec_top(void)
{
  top--;
  return;
}

int get_top(void)
{
  return top;
}


int push(unsigned int *stack, int x)
{
  int r = 0;
  assert(top != SIZE);
  if (top==SIZE) 
  {
    return OVERFLOW;
  } 
  else 
  {
    get_top();
    stack[top] = x;
    inc_top();
  }
  return 0;
}

int pop(unsigned int *stack)
{
  int r = 0;
  assert(0 < top);
  get_top();
  if (top==0) 
  {
    return UNDERFLOW;
  } 
  else 
  {
    dec_top();
    get_top();
    assert(top < SIZE);
    return stack[top];  
  }
}

void *t1(void *arg) 
{
  int i = 0;
  unsigned int tmp;
  int r = 0;
  while (i<SIZE)
  {
    pthread_mutex_lock(&m);
    tmp = __VERIFIER_nondet_uint()%SIZE;
    push(arr,tmp);
    assert(r != OVERFLOW);
    flag=TRUE;
    pthread_mutex_unlock(&m);
    i++;
  }
  return;
}

void *t2(void *arg) 
{
  int i = 0;
  int r = 0;
  while(i<SIZE)
  {
    pthread_mutex_lock(&m);
    if (flag != 0)
    {
      pop(arr);
      assert(r!=UNDERFLOW);

    }
    pthread_mutex_unlock(&m);
    i++;
  }
  return;
}


int main(void) 
{
  pthread_t id1, id2;
  int r = 0;
  pthread_mutex_init(&m, 0);

  pthread_create(&id1, NULL, t1, NULL);
  pthread_create(&id2, NULL, t2, NULL);

  pthread_join(id1, NULL);
  pthread_join(id2, NULL);

  return 0;
}

