import pandas as pd

df = pd.DataFrame({'a': ["a_2_2", "b", "c_1"]})
print(df)
df['a'] = df['a'].str.rsplit('_', n=1).str[0]
print(df)