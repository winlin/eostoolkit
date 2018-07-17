# bpmonitor.py 
#### is used to monitor the rank of bpaccount and calculate the rewards everyday then save into `reward_output` file.

### Implementation:
In the config file, we can supply several API endpoints to query the infomation from the EOS mainnet. Several API endpoints can avoid single point of failure and deferred blocks synchronization. Every endpoint will create a thread and check with mainnet periodically. 

The rewards calculate by of the average vote rate from the last 24 hours. 

The functions have been realized clearly, what you need to do is just rewrite your notification fucntion in ```send_warning()```. The default notification function is using AliSMS service. 

The ```bpmonitor.json``` is easy to be modified and you can add other items by yourself.
