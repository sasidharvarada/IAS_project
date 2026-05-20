# AetherAgents Platform Configuration Design

This document outlines the proposed new configuration file structure for the AetherAgents platform, separating concerns across different stages of the application lifecycle: development, packaging, deployment, instance configuration, and load management.

## 1. Development Time File (`apps/<app_id>/app_config.yaml`)

This file is defined by the application developer. It contains all the necessary information for the application to run, including its artifacts (models, tools, agents, orchestrators), developer-defined global variables, and placeholders for instance-specific variables that will be filled in later.

**Purpose:** To define the application's internal structure and developer-specific settings.

**Content:**
- `app.name`: Unique identifier for the application.
- `app.version`: Application version.
- `app.description`: Brief description of the application.
- `app.author`: Author of the application.
- `app.runtime`: Required runtime (e.g., `python3.11`).
- `artifacts`: Definitions of all models, tools, agents, and orchestrators, including their IDs, classes, and any artifact-specific configurations.
- `global_app_variables`: Key-value pairs for variables that are global to the application and defined by the developer (e.g., default API keys, logging levels).
- `instance_variable_placeholders`: Keys for variables that are instance-specific and will be provided during instance configuration (e.g., `DATABASE_URL`).

**Example File:** `/home/akmal-ali/3rd_year/sem6/ias/final/AetherAgents/apps/email_classifier/app_config.yaml`

## 2. Package Time File (`apps/<app_id>/app_manifest.yaml`)

This file is generated or updated during the application packaging process. It's a standardized manifest that the platform uses to understand the application's core requirements for deployment. It contains information essential for the platform to package and deploy the application correctly.

**Purpose:** To provide a standardized, platform-readable manifest of the application's structure and dependencies.

**Content:**
- `app_id`: Unique identifier for the application.
- `app_version`: Application version.
- `runtime`: Required runtime.
- `entry_point`: The main entry point script for the application (e.g., `main.py`).
- `artifacts`: A simplified list of all artifacts with their types, file paths, and class names, allowing the platform to locate and initialize them.
- `dependencies`: List of dependency files (e.g., `requirements.txt`).
- `global_variable_keys`: A list of global application variable keys that the platform should expect to provide or override.
- `instance_variable_keys`: A list of instance-level variable keys that the platform will provide during instance configuration.

**Example File:** `/home/akmal-ali/3rd_year/sem6/ias/final/AetherAgents/apps/email_classifier/app_manifest.yaml`

## 3. Deployment Global Setup File (`infra/platform_config.yaml`)

This file defines the global configuration of the AetherAgents platform itself. It describes the available infrastructure (VMs), network settings, and system-level services that run independently of any specific application.

**Purpose:** To define the overall platform infrastructure and core services.

**Content:**
- `platform.name`: Name of the platform.
- `platform.version`: Version of the platform.
- `vm_pool`: Definition of master and worker VMs, including IP, username, key file, and resource capacity (CPU, memory).
- `system_services`: Configuration for core platform services like Nginx (for load balancing), Kafka/Zookeeper (for messaging), Lifecycle Manager, and VM Health Checker, including their enabled status and number of nodes/replicas.

**Example File:** `/home/akmal-ali/3rd_year/sem6/ias/final/AetherAgents/infra/platform_config.yaml`

## 4. Instance Level Setup File (`storage/apps/<app_id>/instances/<instance_id>.yaml`)

This file defines a specific instance of a deployed application. An application can have multiple instances, each with its own unique configuration. This file maps instance-specific variables and determines how the application's artifacts are distributed across the available VMs.

**Purpose:** To configure a unique running instance of an application.

**Content:**
- `app_id`: Reference to the deployed application.
- `app_version`: Version of the deployed application.
- `instance_id`: Unique identifier for this application instance.
- `deployment_target_vm`: The primary VM where this instance's core components are deployed.
- `instance_data`: Actual values for instance-specific variables (e.g., `DATABASE_URL`).
- `global_app_variables`: Optional overrides for global application variables defined in `app_config.yaml` or `app_manifest.yaml`.
- `artifact_distribution`: Specifies which VM and port each artifact (model, tool, agent, orchestrator) of this instance will run on.

**Example File:** `/home/akmal-ali/3rd_year/sem6/ias/final/AetherAgents/storage/apps/email_classifier/instances/instance_001.yaml`

## 5. Load Level Setup File (`storage/apps/<app_id>/instances/<instance_id>_load.yaml`)

This file defines the load balancing and auto-scaling settings for a *specific instance* of an application. This configuration is orthogonal to the application's intrinsic definition and allows platform operators to manage resource allocation and responsiveness dynamically.

**Purpose:** To manage the scaling and load behavior of an application instance.

**Content:**
- `app_id`: Reference to the deployed application.
- `instance_id`: Reference to the specific application instance.
- `load_settings.min_instances`: Minimum number of running instances for the application's core components.
- `load_settings.max_instances`: Maximum number of running instances.
- `load_settings.scaling_policy`: Defines the metric (e.g., `cpu_utilization`), threshold, and cooldown period for auto-scaling the instance.
- `load_settings.artifact_scaling`: Optional, fine-grained scaling settings for individual artifacts within the instance, potentially overriding the global instance scaling.

**Example File:** `/home/akmal-ali/3rd_year/sem6/ias/final/AetherAgents/storage/apps/email_classifier/instances/instance_001_load.yaml`
