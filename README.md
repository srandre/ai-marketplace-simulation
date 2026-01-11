# AI Nations: Strategic Resource Game

A turn-based strategy simulation where AI-controlled nations compete to advance through technological eras. Nations autonomously gather resources, construct generators, and negotiate trades using DeepSeek AI for strategic decision-making.

## Overview

Ten nations compete simultaneously to reach the final era (Era of Domination) by accumulating resources and strategically trading with rivals. The first nation to meet Era 3 advancement requirements and transition to Era 4 wins the game.

## Core Mechanics

### Turn Structure

Each nation's turn consists of two sequential phases:

**Trading Phase** (up to 2 trades)
- Propose trades with other nations to acquire needed resources
- If rejected, AI can attempt the same or different trade with an alternative partner
- Nations may skip trading entirely to proceed to building

**Build Phase** (1 generator maximum)
- Construct one generator to automate resource production
- Generators produce resources at the start of each subsequent turn
- Build phase auto-skips if nation cannot afford any available generator

### Resource System

The game uses six resource types with distinct roles:

- GOLD (💰) - Universal trading currency
- WOOD (🪵) - Basic construction material
- STONE (🪨) - Basic construction material
- FOOD (🌾) - Sustenance resource
- TECHNOLOGY (⚙️) - Advanced resource, unlocked in Era 1
- INFORMATION (💾) - Data resource, unlocked in Era 2

### Generators

Generators are permanent buildings that automatically produce resources at turn start. Production scales with the nation's current era.

| Generator | Output | Base Cost | Availability |
|-----------|--------|-----------|--------------|
| Lumber Camp | WOOD | 10 STONE | Era 0+ |
| Quarry | STONE | 10 WOOD | Era 0+ |
| Farm | FOOD | 10 WOOD *or* 10 STONE | Era 0+ |
| Mine | GOLD | 5 WOOD + 5 STONE | Era 0+ |
| Factory | TECHNOLOGY | 100 FOOD + 100 GOLD | Era 1+ |
| Datacenter | INFORMATION | 1000 GOLD + 200 TECHNOLOGY | Era 2+ |

**Progressive Pricing**

Generator costs increase exponentially based on the total number of that generator type built globally across all nations:

```
current_cost = base_cost × 2^(total_built_globally)
```

For example, if 4 Mines exist globally, the 5th Mine costs `(5 WOOD + 5 STONE) × 2^4 = 80 WOOD + 80 STONE`.

### Era System

Nations advance through four eras by accumulating specified resources. Era advancement occurs automatically at turn start when requirements are met.

| Era | Name | Gen. Output | Resources Available | Advancement Reqs |
|-----|------|-------------|---------------------|------------------|
| 0 | Era of Origin | 50/turn | GOLD, WOOD, STONE, FOOD | 50 each basic resource |
| 1 | Era of Industry | 500/turn | + TECHNOLOGY | 500 basic + 200 TECHNOLOGY |
| 2 | Era of Information | 5000/turn | + INFORMATION | 50k basic + 20k TECH + 10k INFO |
| 3 | Era of Domination | 50000/turn | All | Winner |

**Generator Scaling**

When a nation advances eras, all existing generators immediately update to the new era's production rate. A Mine built in Era 0 (50 GOLD/turn) automatically produces 500 GOLD/turn when the nation reaches Era 1, and 5000 GOLD/turn in Era 2.

### Trading System

**Valid Trade Structures:**
- GOLD for resources (e.g., 50 GOLD → 50 WOOD + 30 STONE)
- Resources for GOLD (e.g., 50 WOOD + 30 STONE → 50 GOLD)

**Invalid Trades:**
- Mixing GOLD with resources on the same side
- Same resource on both sides (e.g., GOLD for GOLD)

**Trade Execution:**
1. Initiator proposes trade
2. AI responder evaluates and returns ACCEPT or REJECT
3. If rejected, initiator may retry with different partner or end trading phase
4. Both nations must possess offered resources for trade to execute

Relationship values adjust based on trade outcomes (+1 for successful trades, -1 for failed negotiations).

### AI Decision Framework

Each nation uses DeepSeek AI to make autonomous decisions with access to:

- **Memory**: Previous 10 decisions and their outcomes
- **Full game state**: All nations' current resources and generator inventories
- **Strategic context**: Era advancement requirements and generator costs
- **Natural language reasoning**: AI provides textual explanation for each decision

**Decision Points:**
1. Trading phase - Should I trade? With whom? What to offer for what?
2. Trade response - Should I accept this incoming trade offer?
3. Alternative trade - Trade rejected, retry with different partner or skip?
4. Build phase - Which generator to build given current resources and goals?

## Installation

### Requirements

- Python 3.10 or higher
- DeepSeek API key (obtain from [platform.deepseek.com](https://platform.deepseek.com/))

### Setup

```bash
# Clone repository
git clone <repository-url>
cd ai-marketplace-simulation

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "DEEPSEEK_API_KEY=your_api_key_here" > .env
```

## Usage

Run the simulation:

```bash
python -m src.main
```

### Controls

- **Auto: ON/OFF** - Toggle automatic turn progression with integrated timer
  - ON: Game runs continuously, timer counts up
  - OFF: Game pauses, timer freezes
- **Next Turn** - Manual single-turn advancement (disabled during AI processing or Auto mode)
- **Log entry click** - View full AI reasoning, prompts, and JSON responses
- **Info button (ℹ️)** - Display complete system prompt used for AI decisions
- **Scrolling** - Mouse wheel or scrollbar to navigate game history

## Configuration

Edit `config/game_config.yaml` for customization.

### Game Settings

```yaml
game:
  num_players: 10        # Number of nations (1-50)
  initial_era: 0         # Starting era (0-2)
  initial_turn_number: 1
```

### Era Definitions

```yaml
eras:
  - name: "Era of Origin"
    index: 0
    base_generation: 50
    unlocked_resources: [GOLD, WOOD, STONE, FOOD]
```

### Generator Configuration

```yaml
generators:
  MINE:
    name: "Mine"
    produces: GOLD
    base_cost:
      STONE: 5
      WOOD: 5
    required_era: 0
```

### Era Advancement Thresholds

```yaml
era_advancement:
  era_1_requirements:
    GOLD: 50
    WOOD: 50
    STONE: 50
    FOOD: 50
```

### AI Parameters

```yaml
ai:
  provider: "deepseek"
  model: "deepseek-chat"
  temperature: 0.9          # Randomness (0.0-2.0)
  max_tokens: 1500
  timeout_seconds: 30
```

## Architecture

```
ai-marketplace-simulation/
├── src/
│   ├── ai/
│   │   ├── decision_maker.py      # AI decision orchestration
│   │   └── prompts.py             # Natural language prompt templates
│   ├── game/
│   │   ├── game_controller.py     # Main coordinator
│   │   ├── game_state.py          # State management
│   │   ├── turn_manager.py        # Turn sequencing and automation
│   │   ├── trading.py             # Trade validation and execution
│   │   ├── building.py            # Generator construction
│   │   └── async_turn_executor.py # Background processing
│   ├── models/
│   │   ├── nation.py              # Nation state and operations
│   │   ├── resource.py            # Resource inventory
│   │   ├── generator.py           # Generator blueprints and instances
│   │   ├── transaction.py         # Trade offers and history
│   │   └── enums.py               # Type definitions
│   ├── ui/
│   │   ├── main_window.py         # Main rendering loop
│   │   └── components/            # UI panels and widgets
│   └── utils/
│       └── config.py              # YAML configuration loader
├── config/
│   └── game_config.yaml
├── assets/
│   └── flags/
└── .env                           # API credentials (not tracked)
```

## Event Logging

The game maintains comprehensive logs for all events:

- **AI Decisions** - Strategic choices with natural language reasoning
- **Trade Proposals** - Offers, acceptances, rejections, retries
- **Construction** - Generator builds with resource costs
- **Generation** - Turn-start resource production from all generators
- **Era Progression** - Automatic advancements when thresholds met
- **Victory** - Game conclusion when first nation reaches Era 4

**Log Detail View:**

Click any log entry to inspect:
- Complete prompt sent to DeepSeek API
- Full JSON response with decision and reasoning
- Affected nations and resource changes
- Turn/round timestamps

## Technology Stack

- **Python 3.10+** - Core implementation language
- **Pygame 2.5+** - Rendering and UI framework
- **DeepSeek AI** - Language model for strategic decision-making
- **Pydantic 2.0+** - Runtime type validation and data serialization
- **PyYAML** - Configuration file parsing
- **python-dotenv** - Environment variable management

## Strategy Considerations

Understanding the following mechanics improves AI performance when tuning prompts:

1. **Early Mine Construction**: GOLD serves as universal trading currency, making Mines critical for economic flexibility
2. **Generator Lifetime Value**: Generators built early benefit from era scaling (a Mine built in Era 0 eventually produces 1000x its initial output in Era 3)
3. **Progressive Pricing Impact**: First generator of each type costs base price, fifth costs 16x base, tenth costs 512x base
4. **Generator Trading**: Nations with specific generators can trade surplus production of that resource
5. **Forward Planning**: Building Factories in Era 1 prepares TECHNOLOGY stockpiles needed for Era 2 advancement
6. **Memory Utilization**: AI agents remember previous 10 decisions, allowing them to avoid repeating failed trade patterns

## Victory Condition

The game ends when any nation meets the Era 3 advancement requirements at turn start:
- 50,000 GOLD, WOOD, STONE, FOOD
- 20,000 TECHNOLOGY
- 10,000 INFORMATION

Meeting these thresholds triggers automatic advancement to Era of Domination (Era 4), ending the game with that nation declared winner.

## License

This project is released under the MIT License. See LICENSE file for full terms.

## Contributing

Contributions are welcome. Please open an issue for discussion before submitting significant changes via pull request.
