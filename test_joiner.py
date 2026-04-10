import pygame
from view.menu import MainMenu
pygame.init()
screen = pygame.display.set_mode((800, 600))
menu = MainMenu()
menu.screen = screen
from network_ipc import IPCClient
menu.launch_multiplayer(is_host=False)
