docker build -t prodsim_api_v1 .
docker run -d --name prodsim_api_v1 -p 8000:8000 prodsim_api_v1
@REM docker tag prodsim_api_v1 sebbehrendt/prodsim_api_v1
@REM docker push sebbehrendt/prodsim_api_v1
@REM docker pull sebbehrendt/prodsim_api_v1
@REM docker run -d --name prodsim_api_v1 -p 8000:8000 sebbehrendt/prodsim_api_v1