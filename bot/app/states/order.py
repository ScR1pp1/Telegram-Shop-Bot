from aiogram.fsm.state import State, StatesGroup

class OrderFSM(StatesGroup):
    last_name = State()
    first_name = State()
    patronymic = State()
    
    city = State()
    street = State()
    house = State()
    apartment = State()
    floor = State()
    
    confirmation = State()