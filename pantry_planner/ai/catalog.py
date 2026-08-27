"""A small built-in catalog of everyday dishes for the offline matcher.

These are deliberately generic "use it up" dishes. Ingredient names are the
normalised keys the matcher compares against (see units.normalize_name).
"""

from __future__ import annotations

from .schemas import Candidate

CATALOG: tuple[Candidate, ...] = (
    Candidate(
        "Vegetable stir-fry",
        ("bell pepper", "carrot", "broccoli", "onion", "garlic", "soy sauce", "rice"),
        (
            "Cook the rice.",
            "Slice the vegetables thinly.",
            "Stir-fry garlic and onion, add the rest of the vegetables for 4-5 minutes.",
            "Season with soy sauce and serve over the rice.",
        ),
    ),
    Candidate(
        "Spinach and cheese frittata",
        ("egg", "spinach", "cheddar", "onion", "milk"),
        (
            "Soften the onion in an oven-safe pan.",
            "Wilt the spinach in the pan.",
            "Whisk eggs with milk and cheese, pour over and cook gently.",
            "Finish under the grill until set.",
        ),
    ),
    Candidate(
        "Tomato and basil pasta",
        ("pasta", "tomato", "garlic", "basil", "parmesan"),
        (
            "Boil the pasta.",
            "Cook garlic with chopped tomatoes until saucy.",
            "Toss with the pasta, basil and parmesan.",
        ),
    ),
    Candidate(
        "Egg fried rice",
        ("rice", "egg", "pea", "carrot", "spring onion", "soy sauce"),
        (
            "Use cooked, cooled rice.",
            "Scramble the eggs and set aside.",
            "Fry the vegetables, add the rice and soy sauce, then fold the egg back in.",
        ),
    ),
    Candidate(
        "Red lentil soup",
        ("red lentil", "onion", "carrot", "garlic", "vegetable stock", "cumin"),
        (
            "Soften onion, carrot and garlic.",
            "Add lentils, cumin and stock; simmer 20 minutes.",
            "Blend until smooth and season.",
        ),
    ),
    Candidate(
        "Chickpea and spinach curry",
        ("chickpeas", "spinach", "onion", "tomato", "coconut milk", "curry powder", "rice"),
        (
            "Fry the onion with curry powder.",
            "Add tomatoes, chickpeas and coconut milk; simmer 15 minutes.",
            "Stir in the spinach and serve with rice.",
        ),
    ),
    Candidate(
        "Banana oat pancakes",
        ("banana", "oats", "egg", "milk"),
        (
            "Blend banana, oats, egg and milk into a batter.",
            "Cook small pancakes in a hot pan, 2 minutes a side.",
        ),
    ),
    Candidate(
        "Greek salad",
        ("tomato", "cucumber", "red onion", "feta", "olive", "olive oil"),
        (
            "Chop tomato, cucumber and onion.",
            "Top with feta and olives, dress with olive oil.",
        ),
    ),
    Candidate(
        "Mushroom risotto",
        ("arborio rice", "mushroom", "onion", "vegetable stock", "parmesan", "butter"),
        (
            "Soften onion in butter, then fry the mushrooms.",
            "Toast the rice, then add hot stock a ladle at a time for 18 minutes.",
            "Stir in parmesan and a knob of butter.",
        ),
    ),
    Candidate(
        "Chicken tray bake",
        ("chicken thigh", "potato", "red onion", "bell pepper", "olive oil", "lemon"),
        (
            "Heat the oven to 200 C.",
            "Toss everything with oil, salt and lemon on a tray.",
            "Roast for 40 minutes, turning once.",
        ),
    ),
    Candidate(
        "Black bean tacos",
        ("black beans", "tortilla", "avocado", "lime", "tomato", "red onion"),
        (
            "Warm the beans with a pinch of cumin.",
            "Make a quick salsa with tomato, onion and lime.",
            "Fill warm tortillas with beans, salsa and avocado.",
        ),
    ),
    Candidate(
        "Shakshuka",
        ("egg", "tomato", "bell pepper", "onion", "garlic", "paprika"),
        (
            "Soften onion, pepper and garlic with paprika.",
            "Add tomatoes and simmer 10 minutes.",
            "Make wells, crack in the eggs, cover until just set.",
        ),
    ),
    Candidate(
        "Berry yoghurt smoothie",
        ("yoghurt", "banana", "berry", "milk"),
        ("Blend everything until smooth.",),
    ),
    Candidate(
        "Cheese and tomato toastie",
        ("bread", "cheddar", "tomato", "butter"),
        (
            "Butter the outside of the bread.",
            "Fill with cheese and sliced tomato.",
            "Toast in a pan until golden on both sides.",
        ),
    ),
    Candidate(
        "Leftover vegetable soup",
        ("onion", "carrot", "potato", "celery", "vegetable stock", "zucchini"),
        (
            "Chop whatever vegetables need using.",
            "Simmer in stock for 20 minutes.",
            "Blend or leave chunky, season to taste.",
        ),
    ),
)
