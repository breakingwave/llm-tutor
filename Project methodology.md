### Document gathering
First we prompt an LLM to extract one-line facts about the user from all of the information available, hence constructing a list of 'hooks' to use in the search process. Next we extract the desired material from the user input (e.g. "byzantin empire tax system" from "I want to learn how taxes worked in byzantine empire"). We then construct an array of pairs by appending the material string with a set of hooks that was generated earlier OR by another LLM call (very similar to PAGE paper).  Resulting list is used in the search and retrieval process. 

There are two main sources for that:
1. Open sourced library of educational materials - OpenStax
2. Web search using Tavily

The result is a list of links from Tavily and a set of retrieved chapters from OpenStax. Note: chunking of books might be non-trivial. Another note: can I use googles new embedding model to embed graphics and video? 
The retrieved documents are then scored for relevance against the initial user background and goals with documents not scoring high enough dropped. (Rewrite-Retrieve-Read (Ma et al., EMNLP 2023))

In addition for each selected material there needs to be a summary to use in next steps and to server to the end user

This module is evaluated for relevance to the topic and user background using LLM as a judge approach with cheap LLM and 1-5 scale
### Syllabus generation
Sequential prompting from core concept to curriculum (Instructional Agents, Stanford 2025, GenMentor, WWW 2025). Core approach is similar to IA paper - take ADDIE educational material preparation and drop the last 2 stages. This leaves us with Analyse, Design and Develop steps. Simplified version will collapse the multi-agent interaction into a sequence of LLM calls

> [!NOTE] Implementation sketch
> 
concept_list = llm(ANALYSIS_PROMPT, topic, background, goals, material_summaries)
objectives  = llm(DESIGN_PROMPT, concept_list, material_summaries)
curriculum  = llm(DEVELOP_PROMPT, objectives, materials_chunks)

Concepts is a result of one call, then we do a call for each concept and for curriculum items we do a call for each objective. In the end we have a list of learning items that will be served to the user
User should be able to change the syllabus - drop some learning objectives, ask to add new ones and modify existing ones. 
### LLM serving
Initially content is served as is without any additional modifications. All of the selected content is loaded into the RAG pipeline. While working with certain document user can ask the LLM a question about any of the material and the response will be enriched with actual content and served in a Socratic dialogue-based fashion. For socratic LLM three options should be considered: pure prompting (baseline for midpoint), existing fine-tuned open-sourced LLMs and modification of LLM dialogue structure using steering vectors. Data for the vector could be generated using stronger model and validated in a llm as a judge scenario or by hand
There is a small research hypothesis related to reported performance degradation when fine-tuning for Socratic dialogue (SocraticLM, 2024 report 31% accuracy drop on GSM8K). The hypothesis is that use of steering vectors would have to mitigate that while keeping the dialogue quality intact

### Stack
+ Tavily and OpenStax for materials
+ LiiteLLM for LLM calls routing
+ LlamaIndex and Qdrant for RAG pipeline
+ Separate module for evaluation. Right now only module 1 is evaluated