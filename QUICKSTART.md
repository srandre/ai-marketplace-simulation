# Quick Start Guide

## Installation

1. **Create and activate a virtual environment:**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

## Running the Game

```bash
python -m src.main
```

## Game Controls

- **Auto: ON/OFF** - Toggle automatic turn progression
- **Next Turn** - Manually advance to next turn (disabled during AI processing and in auto mode)
- **View Logs** - Open the game log viewer to see detailed action history

## How It Works

1. **Game Start**: 10 nations are initialized with random starting generators
2. **Turn Flow**:
   - Resource generation from generators
   - Automatic era advancement if requirements are met
   - AI decides actions (sell, buy, build)
   - AI executes trades and construction
3. **AI Decisions**: Each nation uses DeepSeek AI to make strategic decisions
4. **Era Progression**:
   - Era 0 (Origin): Gold, Wood, Stone, Food (10/generator)
   - Era 1 (Structuring): +Technology (100/generator, 10x multiplier)
   - Era 2 (Information): +Information (1000/generator, 100x multiplier)

## Configuration

Edit `config/game_config.yaml` to customize:

- Number of players
- Resource generation rates
- Era advancement requirements
- Generator costs and multipliers
- AI behavior parameters
- UI settings

## Logs and AI Decisions

Click "View Logs" to see:
- All game actions
- Resource generation
- Era advancements
- Trade proposals and results
- Build actions
- **AI Decision Details**: Click on any log entry to see the exact prompt sent to the AI and the response received

## Troubleshooting

**ImportError: No module named 'pygame'**
```bash
pip install pygame
```

**API Connection Issues**
- Check your internet connection
- Verify the DeepSeek API key in `config/game_config.yaml`
- The game will fall back to default actions if API is unavailable

**Game runs too fast in Auto mode**
- Adjust `auto_mode_delay_ms` in `config/game_config.yaml`

## Tips

- Watch how AI nations negotiate trades
- Observe different strategies emerge
- Check relationships between nations in the logs
- See how resource scarcity affects trading behavior
- Notice how nations prioritize era advancement

Enjoy watching the AI nations compete!
