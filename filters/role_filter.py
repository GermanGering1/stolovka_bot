from aiogram.filters import Filter
from aiogram import types

class RoleFilter(Filter):
    """Фильтр для проверки роли пользователя"""
    def __init__(self, role: str):
        self.role = role
    
    async def __call__(self, message: types.Message, user_role: str) -> bool:
        """Проверяет, соответствует ли роль пользователя требуемой"""
        return user_role == self.role

class ManagerFilter(Filter):
    """Фильтр для проверки, является ли пользователь менеджером"""
    async def __call__(self, message: types.Message, user_role: str) -> bool:
        return user_role == 'manager'

class EmployeeFilter(Filter):
    """Фильтр для проверки, является ли пользователь сотрудником"""
    async def __call__(self, message: types.Message, user_role: str) -> bool:
        return user_role == 'employee'

class RegisteredFilter(Filter):
    """Фильтр для проверки, зарегистрирован ли пользователь"""
    async def __call__(self, message: types.Message, user_role: str) -> bool:
        return user_role in ['employee', 'manager']

class PendingFilter(Filter):
    """Фильтр для проверки, ожидает ли пользователь регистрации"""
    async def __call__(self, message: types.Message, user_role: str) -> bool:
        return user_role == 'pending'

class OrderingEnabledFilter(Filter):
    """Фильтр для проверки, доступны ли заказы сегодня"""
    async def __call__(self, message: types.Message, ordering_enabled: bool) -> bool:
        return ordering_enabled

class DeadlineNotPassedFilter(Filter):
    """Фильтр для проверки, не прошел ли дедлайн"""
    async def __call__(self, message: types.Message, deadline_passed: bool) -> bool:
        return not deadline_passed

class CanOrderTomorrowFilter(Filter):
    """Фильтр для проверки, можно ли заказывать на завтра"""
    async def __call__(self, message: types.Message, can_order_tomorrow: bool) -> bool:
        return can_order_tomorrow