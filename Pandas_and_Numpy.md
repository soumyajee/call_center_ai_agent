1. How would you handle missing data in a Pandas DataFrame? Describe at least three strategies.

Missing data in a Pandas DataFrame (represented as NaN, None, or other placeholders) can be handled using several strategies, depending on the dataset and analysis requirements. Here are three common approaches:

    Drop Missing Values: Remove rows or columns containing missing data using dropna(). Suitable when missing data is minimal and dropping it doesn’t significantly reduce the dataset size.
example:
import pandas as pd
df = pd.DataFrame({'A': [1, None, 3], 'B': [4, 5, None]})
# Drop rows with any missing values
df_dropped = df.dropna()
# Drop columns with any missing values
df_dropped_cols = df.dropna(axis=1)
2.2. How would you optimize a large Pandas DataFrame for performance and memory usage?

Optimizing a large Pandas DataFrame involves reducing memory usage and improving computation speed, especially for big datasets. Here are key strategies:

    Use Appropriate Data Types: Downcast numeric types (e.g., float64 to float32, int64 to int8) and use category for columns with limited unique values to save memory.
Example:
import pandas as pd
df = pd.DataFrame({'A': [1, 2, 3], 'B': ['x', 'y', 'x']})
# Downcast numeric columns
df['A'] = pd.to_numeric(df['A'], downcast='integer')  # int8
# Convert to category
df['B'] = df['B'].astype('category')
3. Can you explain broadcasting in NumPy and provide a practical example?

Broadcasting in NumPy allows arrays of different shapes to be used in arithmetic operations by automatically expanding smaller arrays to match the shape of larger ones, without copying data. This enables efficient computation on arrays with compatible shapes.

    Rules:
        Arrays must have the same number of dimensions, or one can have fewer dimensions (NumPy prepends singleton dimensions).
        Dimensions are compatible if they are equal or one is 1.
        NumPy stretches dimensions of size 1 to match the other array’s size.
    Practical Example: Normalize a matrix by subtracting the mean of each row.
Example:
import numpy as np
# 3x4 matrix
matrix = np.array([[1, 2, 3, 4],
                   [5, 6, 7, 8],
                   [9, 10, 11, 12]])
# Compute row means (shape: (3,))
row_means = np.mean(matrix, axis=1)
# Broadcast row_means (3,) to (3,4) to subtract from each element
normalized = matrix - row_means[:, np.newaxis]
print(normalized)
output:
[[-1.5 -0.5  0.5  1.5]
 [-1.5 -0.5  0.5  1.5]
 [-1.5 -0.5  0.5  1.5]]            