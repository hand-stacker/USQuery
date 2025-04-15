let AI_generated_content = document.getElementById('AI_generated_content').textContent;
let AI_warning = document.getElementById("AI_warning");
if (AI_generated_content == '"F"') {
    AI_warning.remove();
}