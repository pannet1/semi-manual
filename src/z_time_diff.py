import pendulum

# Given IST datetime string
order_time = "2024-11-21 14:17:46+05:30"

# Parse order_time into a pendulum datetime object
parsed_datetime = pendulum.parse(order_time)

# Get the current datetime in Asia/Kolkata timezone
current_datetime = pendulum.now("Asia/Kolkata")

# Compare the two datetimes
if parsed_datetime > current_datetime:
    print("order_time is greater than the current time.")
else:
    print("order_time is not greater than the current time.")
