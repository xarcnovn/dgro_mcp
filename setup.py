"""
Setup script for the MCP client
"""

from setuptools import setup, find_packages

# Read version from package
with open("mcp_client/__init__.py", "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"\'')
            break
    else:
        version = "0.1.0"

# Read README for long description
try:
    with open("README.md", "r") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "MCP Client - A client library for connecting to MCP servers"

setup(
    name="mcp_client",
    version=version,
    description="MCP Client - A client library for connecting to MCP servers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/mcp_client",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "aiohttp>=3.8.0",
        "fastapi>=0.95.0",
        "uvicorn>=0.22.0",
        "websockets>=11.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mcp_client=mcp_client.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
) 