#!/bin/bash

echo "======================================"
echo "Essay Search Engine - Setup"
echo "======================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    echo "Please install Python 3.9 or later"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create venv
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
echo "(This may take several minutes)"
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error: Failed to install Python dependencies"
    exit 1
fi

echo ""
echo "✓ Python dependencies installed"

# Create data directories
echo ""
echo "Creating data directories..."
mkdir -p private/books
mkdir -p public/data
mkdir -p public/chunks

echo "✓ Data directories created"

# Download sentence-transformers model
echo ""
echo "======================================"
echo "Downloading embedding model..."
echo "======================================"
echo ""
echo "Model: BAAI/bge-large-en-v1.5 (~1.3GB)"
echo "This will take several minutes..."
echo ""
python3 -c "from sentence_transformers import SentenceTransformer; print('Loading model...'); model = SentenceTransformer('BAAI/bge-large-en-v1.5'); print('✓ Model downloaded and cached')"

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Warning: Failed to download embedding model"
    echo "   The model will be downloaded when you first run sync"
fi

# Check Ollama
echo ""
echo "======================================"
echo "Checking Ollama..."
echo "======================================"
echo ""

if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama is not installed"
    echo ""
    echo "   Ollama is required for processing books (generates semantic tags)"
    echo ""
    echo "   Setup instructions:"
    echo "   1. Install Ollama from: https://ollama.ai"
    echo "   2. Start Ollama: ollama serve"
    echo "   3. Pull model: ollama pull qwen2.5:7b"
    echo ""
else
    echo "✓ Ollama installed: $(ollama --version)"

    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✓ Ollama is running"

        # Check if qwen2.5:7b is available
        if ollama list | grep -q "qwen2.5:7b"; then
            echo "✓ qwen2.5:7b model available"
        else
            echo ""
            echo "⚠️  qwen2.5:7b model not found"
            echo "   Pulling model now (this may take several minutes)..."
            echo ""
            ollama pull qwen2.5:7b

            if [ $? -eq 0 ]; then
                echo "✓ qwen2.5:7b model downloaded"
            else
                echo "❌ Failed to pull qwen2.5:7b model"
                echo "   Please run manually: ollama pull qwen2.5:7b"
            fi
        fi
    else
        echo "⚠️  Ollama is not running"
        echo "   Start it with: ollama serve"
        echo "   Then pull the model: ollama pull qwen2.5:7b"
    fi
fi

# Summary
echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Add books:"
echo "   ./lib <book.epub>"
echo ""
echo "2. Sync to web:"
echo "   ./lib --sync"
echo ""
echo "3. Install frontend dependencies:"
echo "   npm install"
echo ""
echo "4. Test locally:"
echo "   npm run dev"
echo ""
echo "5. Build for production:"
echo "   npm run build"
echo ""
echo "Commands:"
echo "  ./lib --help     Show all commands"
echo "  ./lib --list     List indexed books"
echo ""
