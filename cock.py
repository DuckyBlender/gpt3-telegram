import asyncio
from datetime import datetime, timedelta

async def every_midnight():
    while True:
        # Get the current time
        now = datetime.now()
        
        # Calculate the time until the next midnight
        next_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        time_until_midnight = next_midnight - now
        
        # Wait until midnight
        await asyncio.sleep(time_until_midnight.total_seconds())
        
        # Run the function at midnight
        print("Midnight has arrived!")

# Start the task
async def main():
    task = asyncio.create_task(every_midnight())
    await task
    
# Run the main function
asyncio.run(main())