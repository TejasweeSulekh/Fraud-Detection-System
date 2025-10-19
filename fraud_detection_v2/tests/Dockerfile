# Use the same Python base as our other services for consistency
FROM python:3.9-slim

# Set a working directory
WORKDIR /code

# Copy the requirements file
COPY ./requirements.txt /code/requirements.txt

# Install the test dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the test code
COPY . /code/

# The default command (which we will override)
# We just need it to wait until we're ready to run tests.
CMD ["tail", "-f", "/dev/null"]