FROM python:3.12-slim

# keep a clean, explicit workdir
WORKDIR /opt/devtube

# copy the package as a folder so "app" remains a package
COPY app/ /opt/devtube/app/

# install deps
RUN pip install --no-cache-dir -r /opt/devtube/app/requirements.txt

EXPOSE 5000
ENV FLASK_ENV=production

# run as a module so relative imports always work
CMD ["python", "-m", "app.main"]
