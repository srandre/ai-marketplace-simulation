# AI Nations: Strategic Resource Game

An AI-driven turn-based strategy game where nations compete to advance through eras by gathering resources, building generators, and engaging in diplomatic trade.

## Features

- **10 AI-controlled Nations** playing autonomously using DeepSeek AI
- **6 Resource Types**: Gold (💰), Wood (🪵), Stone (🪨), Food (🌾), Technology (⚙️), Information (💾)
- **3 Progressive Eras**: Origin → Structuring → Information
- **Dynamic Economy**: Progressive pricing and resource generation
- **Diplomatic Relations**: Nations remember trade history and build relationships
- **Real-time Visualization**: Watch AI nations compete in a beautiful Pygame interface

## Game Mechanics

### Eras and Resources
- **Era of Origin**: Gold, Wood, Stone, Food (10 units/generator)
- **Era of Structuring**: Unlocks Technology (100 units/generator, 10x multiplier)
- **Era of Information**: Unlocks Information (1000 units/generator, 10x multiplier)

### Turn Structure
Each nation can perform up to 3 actions per turn:
1. **Sell Resources** (trade with other nations)
2. **Buy Resources** (trade with other nations)
3. **Build Generator** (construct resource-producing buildings)

### Generators and Pricing
- **Lumber Camp** (Wood): 10 Stone (base)
- **Quarry** (Stone): 10 Wood (base)
- **Farm** (Food): 10 of any resource (base)
- **Mine** (Gold): 5 Stone + 5 Wood (base)
- **Factory** (Technology): 100 Food + 100 Gold (base)
- **Datacenter** (Information): 1000 Gold + 200 Technology (base)

Prices increase progressively: 1st generator = base price, 2nd = 2x, 3rd = 3x, etc.

### Diplomacy
- Successful trades: +1 relationship
- Failed negotiations: -1 relationship
- AI considers relationships when making offers

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config/game_config.yaml` to customize:
- Number of players
- Resource generation rates
- Era advancement requirements
- Generator costs and multipliers
- AI behavior parameters

## Running the Game

```bash
python -m src.main
```

## Controls

- **Start/Stop Auto Mode**: Toggle automatic turn progression
- **Next Turn**: Manually advance to next turn (disabled during AI thinking)
- **View Logs**: Open detailed game log with AI decision insights

## Project Structure

```
ai-marketplace-simulation/
├── src/
│   ├── models/          # Game entities (Nation, Resource, Generator)
│   ├── game/            # Game logic and state management
│   ├── ai/              # AI decision-making with DeepSeek
│   ├── ui/              # Pygame interface components
│   └── utils/           # Utilities and helpers
├── config/              # Configuration files
└── assets/              # Images, fonts, icons
```

## Technologies

- **Python 3.10+**
- **Pygame**: Game interface and rendering
- **DeepSeek AI**: Nation decision-making
- **YAML**: Configuration management
- **Pydantic**: Data validation