#!/bin/bash
if [ ! -f ./docker-compose.yml ]; then
  echo "Please change path into docker-compose directory"
  exit 1
fi

DOCKERSNAME="nodeosd"
CLI="cleos"            
TOKEN="EOS"             
TOKENSC="eosio.token"   
WALLETPASS=""
PRODUCER=""
VOTEDPROS="$PRODUCER"
ACTION="vote"  # 'buyram' or 'vote'

NODEOSPORT=80
WALLETPORT=8888
CLICMD="sudo docker-compose exec -T ${DOCKERSNAME} ${CLI} -u http://localhost:${NODEOSPORT} --wallet-url http://localhost:${WALLETPORT}"

echo $WALLETPASS | $CLICMD wallet unlock
if [ $? -ne 0 ]; then
  echo "ERROR: Failed to unlock wallet"
  exit 1
fi
$CLICMD system claimrewards $PRODUCER
if [ $? -ne 0 ]; then
  echo "ERROR: Failed to claimrewards"
fi

balance=`$CLICMD get currency balance $TOKENSC $PRODUCER`
if [ -z "${balance// }" ]; then
  echo "WARNING: balance is empty, so will exist this time"
  exit 0
fi

ary=(${balance// / })
halfnumber=`echo "$ary/2.0" | bc`
number=""
printf -v number "%.04f $TOKEN" $halfnumber
echo "balance:$balance $number"

if [ $ACTION == "vote" ]; then
  $CLICMD system delegatebw $PRODUCER $PRODUCER "$number" "$number"
  $CLICMD system voteproducer prods $PRODUCER $VOTEDPROS
elif [ $ACTION == "buyram" ]; then
  $CLICMD system buyram $PRODUCER $PRODUCER "$balance"
fi
$CLICMD wallet lock
