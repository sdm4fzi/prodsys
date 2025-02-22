docker build -t sebbehrendt/prodsys .
docker run -d --name prodsys -p 8000:8000 sebbehrendt/prodsys
@REM docker push sebbehrendt/prodsys
@REM docker pull sebbehrendt/prodsys
@REM docker run -d --name prodsys -p 8000:8000 sebbehrendt/prodsys