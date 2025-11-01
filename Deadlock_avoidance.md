# How to avoid Deadlocks in the simulation

1. Production requests with a target that has full input queues (no place to put) are tabu. Routers do not route to them, because they are full. 
2. Controllers don't start transports to target queue which are full. This should not happen, due to 1, but if transport have happened in the mean-time, this request can be infeasible now. These requests are put back to the router to reroute.
3. Lots can be formed but must avoid overfilling the target queues, both for production and transport processes. When lots are formed, they consider to have the same target_quueue to not uncosider reservations.
4. reservations of queues get an id and must be shown, if wrong or not reserved, an error is thrown. 
