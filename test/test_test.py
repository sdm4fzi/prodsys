class A:
    def a(self):
        print("this is it")

example_a = A()
c = getattr(example_a, 'a')
c()