"""Entertainment skills for MARS - jokes, facts, quotes, and games."""

import random
import subprocess
from typing import Optional

import requests


JOKES: list[str] = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?'",
    "Why do Java developers wear glasses? Because they don't C#!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the programmer quit his job? Because he didn't get arrays.",
    "What's a computer's favorite snack? Microchips!",
    "I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.",
    "Why was the JavaScript developer sad? Because he didn't Node how to Express himself.",
    "A programmer's partner says 'Go to the store, get a gallon of milk, and if they have eggs, get a dozen.' The programmer comes back with 12 gallons of milk.",
    "Why don't programmers like nature? It has too many bugs.",
    "What did the ocean say to the beach? Nothing, it just waved.",
    "Why don't scientists trust atoms? Because they make up everything!",
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them.",
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fake noodle? An impasta!",
    "Why can't you give Elsa a balloon? Because she'll let it go.",
    "What's the best thing about Switzerland? I don't know, but the flag is a big plus.",
    "Did you hear about the claustrophobic astronaut? He just needed a little space.",
    "Why did the bicycle fall over? Because it was two-tired!",
    "I used to hate facial hair, but then it grew on me.",
    "Why did the math book look so sad? Because it had too many problems.",
    "What do you call cheese that isn't yours? Nacho cheese!",
]

FACTS: list[str] = [
    "Honey never spoils. Archaeologists have found 3,000-year-old honey in Egyptian tombs that was still edible.",
    "A group of flamingos is called a flamboyance.",
    "The shortest war in history lasted 38 to 45 minutes — between Britain and Zanzibar in 1896.",
    "Octopuses have three hearts and blue blood.",
    "A day on Venus is longer than a year on Venus.",
    "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
    "The human nose can detect over 1 trillion different scents.",
    "Bananas are technically berries, but strawberries are not.",
    "The average person walks about 100,000 miles in their lifetime — enough to circle the Earth four times.",
    "There are more possible iterations of a game of chess than there are atoms in the observable universe.",
    "Wombat droppings are cube-shaped — the only known animal to produce cube-shaped feces.",
    "The Great Wall of China is not visible from space with the naked eye.",
    "A bolt of lightning is five times hotter than the surface of the sun.",
    "Crows can recognize human faces and hold grudges.",
    "The shortest complete sentence in English is 'Go.'",
    "Sharks are older than trees — they've been around for about 450 million years.",
    "A snail can sleep for three years at a time.",
    "The dot over the letters 'i' and 'j' is called a tittle.",
    "It is impossible to hum while holding your nose closed.",
    "A group of cats is called a clowder.",
]

QUOTES: list[str] = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "In the middle of every difficulty lies opportunity. — Albert Einstein",
    "It does not matter how slowly you go as long as you do not stop. — Confucius",
    "Life is what happens when you're busy making other plans. — John Lennon",
    "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
    "Strive not to be a success, but rather to be of value. — Albert Einstein",
    "Two roads diverged in a wood, and I took the one less traveled by. — Robert Frost",
    "I have not failed. I've just found 10,000 ways that won't work. — Thomas Edison",
    "The only impossible journey is the one you never begin. — Tony Robbins",
    "In three words I can sum up everything I've learned about life: it goes on. — Robert Frost",
    "You miss 100% of the shots you don't take. — Wayne Gretzky",
    "Whether you think you can or you think you can't, you're right. — Henry Ford",
    "The best time to plant a tree was 20 years ago. The second best time is now. — Chinese Proverb",
    "An unexamined life is not worth living. — Socrates",
    "Spread love everywhere you go. Let no one ever come to you without leaving happier. — Mother Teresa",
    "When you reach the end of your rope, tie a knot in it and hang on. — Franklin D. Roosevelt",
    "Always remember that you are absolutely unique. Just like everyone else. — Margaret Mead",
    "Don't judge each day by the harvest you reap but by the seeds that you plant. — Robert Louis Stevenson",
    "The purpose of our lives is to be happy. — Dalai Lama",
    "Get busy living or get busy dying. — Stephen King",
    "You only live once, but if you do it right, once is enough. — Mae West",
    "Many of life's failures are people who did not realize how close they were to success when they gave up. — Thomas Edison",
    "You have brains in your head. You have feet in your shoes. You can steer yourself any direction you choose. — Dr. Seuss",
]


def tell_joke() -> str:
    """Return a random joke, optionally fetched from an online API.

    Returns:
        A joke as a string.
    """
    try:
        response = requests.get(
            "https://official-joke-api.appspot.com/random_joke", timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            return f"{data['setup']} ... {data['punchline']}"
    except Exception:
        pass
    return random.choice(JOKES)


def get_random_fact() -> str:
    """Return an interesting random fact, optionally from the Numbers API.

    Returns:
        A random fact as a string.
    """
    try:
        response = requests.get("http://numbersapi.com/random/trivia", timeout=3)
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass
    return random.choice(FACTS)


def get_quote() -> str:
    """Return a random inspirational quote.

    Returns:
        An inspirational quote as a string.
    """
    try:
        response = requests.get(
            "https://zenquotes.io/api/random", timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list):
                return f"{data[0]['q']} — {data[0]['a']}"
    except Exception:
        pass
    return random.choice(QUOTES)


def play_rock_paper_scissors(choice: str) -> str:
    """Play Rock, Paper, Scissors against MARS.

    Args:
        choice: Player's choice — 'rock', 'paper', or 'scissors'.

    Returns:
        Result of the game as a string.
    """
    options = ["rock", "paper", "scissors"]
    choice = choice.strip().lower()
    if choice not in options:
        return f"Invalid choice '{choice}'. Please choose rock, paper, or scissors."

    computer = random.choice(options)
    if choice == computer:
        result = "It's a tie"
    elif (
        (choice == "rock" and computer == "scissors")
        or (choice == "paper" and computer == "rock")
        or (choice == "scissors" and computer == "paper")
    ):
        result = "You win"
    else:
        result = "I win"

    return f"You chose {choice}, I chose {computer}. {result}!"


def flip_coin() -> str:
    """Flip a coin and return the result.

    Returns:
        'Heads' or 'Tails' as a string.
    """
    result = random.choice(["Heads", "Tails"])
    return f"The coin landed on {result}!"


def roll_dice(sides: int = 6) -> str:
    """Roll a dice with the given number of sides.

    Args:
        sides: Number of sides on the dice (default 6).

    Returns:
        The result of the dice roll as a string.
    """
    if sides < 2:
        return "A dice must have at least 2 sides."
    result = random.randint(1, sides)
    return f"Rolling a {sides}-sided dice... You rolled a {result}!"
