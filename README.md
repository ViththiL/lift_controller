# element_lift_controller
This contain the sources of Element Lift Controllers for different lift manufacturers  

## PLC login details of Sesto user
User  : Admin
Password : 100%sesto

## PLC login details of St Andrew user
User  : ST-ANDREWS-USER
Password : 149380


# Tango Door Controller
To send door commands:
POST - http://172.16.40.159:3001/smart_door/remote_operation

Body: 
{"door_id": "Door1", "mode": 0}

mode = 0 for closing 
mode = 2 for opening

To check the door state:
GET - http://172.16.40.159:3001/smart_door/door_status

# Tango Lift Controller
To send door commands:
POST - http://172.16.40.159:3001/smart_lift/remote_operation

Body:
{
    "destination_floor": "L2", 
    "lift_id": "Lift1",
    "request_type": 1
}

Destination floor can either be L1 or L2

To get the lift status:
GET - http://172.16.40.159:3001/smart_lift/lift_status
