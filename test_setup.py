#!/usr/bin/env python3
"""Setup verification script - Tests all components before running the service."""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required packages are installed."""
    print("Testing imports...")
    errors = []
    
    try:
        import mcp
        print("  ✅ mcp")
    except ImportError as e:
        errors.append(f"  ❌ mcp: {e}")
    
    try:
        import gitlab
        print("  ✅ python-gitlab")
    except ImportError as e:
        errors.append(f"  ❌ python-gitlab: {e}")
    
    try:
        import aiohttp
        print("  ✅ aiohttp")
    except ImportError as e:
        errors.append(f"  ❌ aiohttp: {e}")
    
    try:
        from dotenv import load_dotenv
        print("  ✅ python-dotenv")
    except ImportError as e:
        errors.append(f"  ❌ python-dotenv: {e}")
    
    return errors


def test_configuration():
    """Test configuration file exists and is valid."""
    print("\nTesting configuration...")
    errors = []
    
    env_file = Path(".env")
    if not env_file.exists():
        errors.append("  ❌ .env file not found. Copy config.example.env to .env")
        return errors
    
    print("  ✅ .env file exists")
    
    from src.utils.config import Config
    
    try:
        config = Config.from_env()
        print(f"  ✅ Configuration loaded")
        
        # Validate
        config_errors = config.validate()
        if config_errors:
            for err in config_errors:
                errors.append(f"  ❌ {err}")
        else:
            print("  ✅ Configuration valid")
            print(f"     GitLab URL: {config.gitlab_url}")
            print(f"     Gmail: {config.gmail_email}")
            print(f"     Ollama Model: {config.ollama_model}")
    
    except Exception as e:
        errors.append(f"  ❌ Error loading config: {e}")
    
    return errors


def test_ollama():
    """Test Ollama connection."""
    print("\nTesting Ollama...")
    errors = []
    
    try:
        import aiohttp
        import asyncio
        
        async def check_ollama():
            from src.utils.config import Config
            config = Config.from_env()
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{config.ollama_base_url}/api/tags",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            models = data.get("models", [])
                            print(f"  ✅ Ollama is running")
                            print(f"     Available models: {len(models)}")
                            
                            # Check if configured model exists
                            model_names = [m.get("name", "") for m in models]
                            if config.ollama_model in model_names:
                                print(f"  ✅ Model '{config.ollama_model}' is available")
                            else:
                                return [f"  ⚠️  Model '{config.ollama_model}' not found. Run: ollama pull {config.ollama_model}"]
                            
                            return []
                        else:
                            return [f"  ❌ Ollama returned status {response.status}"]
            except asyncio.TimeoutError:
                return ["  ❌ Ollama connection timeout. Is it running? (ollama serve)"]
            except Exception as e:
                return [f"  ❌ Ollama error: {e}"]
        
        errors = asyncio.run(check_ollama())
    
    except Exception as e:
        errors.append(f"  ❌ Error testing Ollama: {e}")
    
    return errors


def test_gitlab():
    """Test GitLab connection."""
    print("\nTesting GitLab...")
    errors = []
    
    try:
        from src.utils.config import Config
        from src.utils.gitlab_client import GitLabClient
        
        config = Config.from_env()
        
        if not config.gitlab_token:
            errors.append("  ❌ GitLab token not configured")
            return errors
        
        try:
            client = GitLabClient(config.gitlab_url, config.gitlab_token)
            print(f"  ✅ Connected to GitLab")
            print(f"     URL: {config.gitlab_url}")
        except Exception as e:
            errors.append(f"  ❌ GitLab connection failed: {e}")
    
    except Exception as e:
        errors.append(f"  ❌ Error testing GitLab: {e}")
    
    return errors


def test_gmail():
    """Test Gmail connection."""
    print("\nTesting Gmail...")
    errors = []
    
    try:
        import imaplib
        from src.utils.config import Config
        
        config = Config.from_env()
        
        if not config.gmail_email or not config.gmail_app_password:
            errors.append("  ❌ Gmail credentials not configured")
            return errors
        
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(config.gmail_email, config.gmail_app_password)
            mail.select("inbox")
            print("  ✅ Connected to Gmail")
            print(f"     Email: {config.gmail_email}")
            mail.close()
            mail.logout()
        except imaplib.IMAP4.error as e:
            errors.append(f"  ❌ Gmail authentication failed: {e}")
            errors.append("     Make sure you're using an app-specific password")
        except Exception as e:
            errors.append(f"  ❌ Gmail connection failed: {e}")
    
    except Exception as e:
        errors.append(f"  ❌ Error testing Gmail: {e}")
    
    return errors


def main():
    """Run all tests."""
    print("=" * 60)
    print("GitLab MR Summarizer - Setup Verification")
    print("=" * 60)
    
    all_errors = []
    
    # Test imports
    all_errors.extend(test_imports())
    
    # Test configuration
    all_errors.extend(test_configuration())
    
    # Test external services
    all_errors.extend(test_ollama())
    all_errors.extend(test_gitlab())
    all_errors.extend(test_gmail())
    
    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print("❌ Setup verification FAILED")
        print("=" * 60)
        print("\nErrors found:")
        for error in all_errors:
            print(error)
        print("\nPlease fix the errors above before running the service.")
        return 1
    else:
        print("✅ Setup verification PASSED")
        print("=" * 60)
        print("\nAll checks passed! You can now run:")
        print("  python main.py")
        return 0


if __name__ == "__main__":
    sys.exit(main())

