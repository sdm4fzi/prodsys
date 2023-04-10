docker build -t prodsim_test .
docker run -d --name prodsim -p 8000:8000 prodsim_test