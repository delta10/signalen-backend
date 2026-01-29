# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2024 Gemeente Amsterdam
"""
Constants for the classification app.
"""

# File types supported by the import_model command
CLASSIFICATION_FILE_TYPES = [
    'main-model', 
    'main-slugs', 
    'sub-model', 
    'sub-slugs'
]

# Maximum file size for model imports (100MB)
MAX_MODEL_FILE_SIZE = 100 * 1024 * 1024

# Training status choices
TRAINING_STATUS_RUNNING = "RUNNING"
TRAINING_STATUS_COMPLETED = "COMPLETED" 
TRAINING_STATUS_FAILED = "FAILED"