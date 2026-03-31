### Abstract
Artificial Intelligence in general and LLMs in particular already have a significant impact on our daily lives, although they never became a big part of the industries with the highest social impact - healthcare and education. The potential of LLMs to change education is enourmous, however current applications lack structure and adaptation to each individual user. The proposed system will act as a personal tutor that will be able to research for the material and serve it based on the user's background and long-term learning goals. Core techniques used are deep research, RAG and fine-tuning for specific dialogue form. Final system components include:

1. Deep Research to gather relevant study materials
2. Curriculum generation with learning objectives and preparation of study materials for RAG
3. LLM fine-tuned for socratic dialogue to serve the curriculum with regards to user's background
### Literature review

Overall improvement in learning process: [LLMs in education]

**Agentic educational retrieval.** Agentic search systems are progressing rapidly but lack adaptation for educational context. Comprehensive review of agentic retrieval classifies it as a pretty hard task [Can Deep Research Agents Retrieve and Organize?]. This part of the project is the most scientifically novel and hard to evaluate. There were no examples found of incorporation of a learner model in the search process.

**Curriculum generation.** This component has much more work on it, one of the most prominent examples is [Instructional Agents](https://scale.stanford.edu/ai/repository/instructional-agents-llm-agents-automated-course-material-generation-teaching) which uses multi-agent framework to generate complete course packages. Other papers include: GenMentor (WWW 2025) maps goals → skills → materials via fine-tuned LLM with Bing search and Pxplore (Lim et al., 2025) applies RL for learning path planning from raw dialogue logs. 

**Socratic dialogue.** Most research is math-centric. SocraticLM (NeurIPS 2024) constructs a 35K multi-turn dialogue dataset of teacher-student interactions and fine-tunes Qwen2.5-7B. SocraticLLM (Ding et al., CIKM 2024) fine-tunes Qwen1.5-7B on SocraticMATH using Socratic prompts and knowledge injection. Most of the work is done using fine-tuning over specialised dataset.

**Evaluation.** No standardised dataset exists. Typical evaluation is by utilising LLM-as-a-Judge or human evaluators to rate based on pre-defined rubrick. The sample size is in hundreds (e.g. 150 for SocraticLLM)

### Industry review
Individual components exists in open-source, startup products and corporate offerings

**Khanmigo** (Khan Academy): most widely deployed multi-domain Socratic tutor (2M+ users), prompt-engineered GPT-4. Does retrieval + dialogue but relies on human-curated content - no automated curriculum generation or web retrieval.

**Google LearnLM**: Gemini fine-tune for pedagogy. Supports RAG over uploaded materials and web search but lacks curriculum structuring or learning goals component.

**Learning modes** (ChatGPT, Claude, Gemini): dialogue-level modifications for teaching - no retrieval or structuring.

**DeepTutor**: open-source (9.5k stars), multi-agent deep research + educational personalisation. 

**EduPlanner:** RAG over uploaded materials + curriculum generation.

**The gap:** existing systems do 2 of 3 well. RAG + Dialogue is common. Structuring + Dialogue exists with pre-loaded content. Retrieval + Structuring barely exists in education. No system chains all three end-to-end for arbitrary domains.
### Mockup

### Proposed method

Three chained modules: 
1. Learner-Aware Agentic Research
2. Automated Curriculum Generator
3. Socratic Dialogue Engine with RAG
 
User input feeds modules (1) and (2). Module (1) outputs filtered materials to (2), which produces learning objectives and chunked content for (3)'s RAG store. Module (3) delivers interactive tutoring.

Baseline version of the modules heavily relies on existing open-source solutions
#### Module 1 - Gather the materials
Modifies open-source deep research system to serve as a web crawler to gather relevant materials. Fulfils the task in the following steps:

1. Query generation: decompose the topic into sub-queries (what to look for) based on user's background and learning objective. Materials are conditioned not only by topic but how intense they should be
2. Web search: classic API tool use using sub-queries from step 1. The goal is to gather initial set of materials
3. Filtering: skim through the materials and check them against relevance for user background and learning objectives. Discard the unfitting documents, tune the sub-queries
4. Repeat until out of budget/converged
#### Module 2 - Generate curriculum
1. Use existing open-source system to construct learning objectives based on user background and learning objectives
2. Use existing approaches to automatically generate curriculum based on output of step 1
3. Create associations between materials retrieved by module 1 and the curriculum from step 2
4. Chunk and index the materials based on associative split from step 3. Load the chunks into a retriever-friendly database
#### Module 3 - serve via Socratic dialogue
1. As a baseline - use existing fine-tuned versions of open-sourced models as a baseline for serving LLM
	1. Enhance the baseline with:
		1. New training dataset generated via student-tutor appoarch using strong model. The dataset should enhance the existing math-centric capabilities to broader domain spectrum. Focus on 2-3 new domains
		2. Test the steering vector approach instead of fine-tuning. Generate the data using the same student-tutor approach with strong model as a baseline
		3. Evaluate using LLM-as-a-Judge with rubrics and classmates assistance
2. Answer arbitrary user question about the material with precision using RAG with retriever compiled by module 2
3. Student-facing UI - progression over the curriculum, learning curves

### Midpoint goals
Initial goal is to make the entire pipeline functional with baseline open-source components:

  + Baseline versions of all modules are up and running
  + End-to-end pipeline is available online and configurable for further expirementation
  + Modules will be implemented in reverse order:
	  1. Module 3 - existing fine-tunes versions of 'Socratic' tutoring LLMs
	  2. Module 2 - upload own materials and enrich Module 3 with RAG and curriculum generation
	  3. Module 1 - gather relevant materials using deep research
### End goals
  + Another round of fine-tuning using LoRA and non-math dataset (needs to be generated)
	  + Vector steering experiment results
  + Propose and implement an evaluation mechanism for module 1
  + Ablations Socratic only vs retrieval + Socratic vs full pipeline conducted by author, fellow students and (if willing) course staff
	  + Specifically evaluate on math and non-math domains chosen for adaptation of module 3

### Engagement with course material

This project builds on the material from the first half of the course:
1. Prompt engineering for all modules
2. Agentic deep research and reasoning - build the system based on open-sourced components
3. Fine-tuning and vector steering experimentation
4. RAG system deployment, support for user document uploads
### Use of AI
+ Research of relevant papers (around 70% of listed were initially found by Opus4.5,)
+ Generation of Mockup diagram from my hand-drawn sketch
+ Brainstorming of how exactly the system might look like
+ Fixing grammar, writing and LaTex formatting of the final work
+ Reference section generation 