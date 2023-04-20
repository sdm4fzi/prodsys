# Scenarios and naming conventions

There exist four dimensions of scenarios:
- production system capacity (e.g. more product and more production capacity)
- length of process chains (e.g. more steps)
- product variety
- process time variance

We perform a design of experiment as follows:
- We define two configuration with high, medium and low process time variance (index X: L, M, H)
- for each of the three scenarios we perform at first a study with larger production capacity (index: X1, X2a, X2b)
- then we compare the the three scenarios L, M, H with different length of process chains (index: X3a, X3b)
- finally we compare the the three scenarios L, M, H with different product variety (index: X4a, X4b)

# Scenario H - high process time variance

H1: 
- 1100 products (producs 1) in 50 hours
- 6 possible machines
- 5 steps in process chain
- 1 product variant


## Variation of production system capacity

H2a: 1100 products (product 1) in 28 hours and 7 possible machines
H2b: 1100 products (product 1) in 26 hours and 8 possible machines

## Variation of process chain length

H3a: 1100 products (product 1) with 7 process steps in 60 hours
H3b: 1100 products  (product 1) with 9 process steps in 60 hours

## Variation of product variety

H4a: 740 product 1, 600 product 2 in 50 hours
H4b: 650 product 1, 500 product 2, 525 product 3 in 50 hours

A partial scenario considers only some transformations, namely: transport capacity, layout, sequencing logic and routing logic.
