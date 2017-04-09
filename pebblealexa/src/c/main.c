#include <pebble.h>
#define paddingX 4
#define paddingY 4
#define maxH 2000
#define STRING 1

Window *window;
ScrollLayer *scrollL;
TextLayer *textL;
char *text;
ScrollLayerCallbacks cbacks;

static DictationSession *s_dictation_session;
static char s_last_text[512];






void scroll_text_init(char* text_);
void scroll_text_destroy();
void scroll_text_show(bool animate);
void scroll_text_reload();



static void in_received_handler(DictionaryIterator *iter, void *context) {
  Tuple *str_tuple = dict_find(iter, STRING);
	if(str_tuple){
		text = str_tuple->value->cstring;
		scroll_text_reload();
	}
}

static void in_dropped_handler(AppMessageResult reason, void *context) {
  APP_LOG(APP_LOG_LEVEL_DEBUG, "App Message Dropped!");
}

static void out_failed_handler(DictionaryIterator *failed, AppMessageResult reason, void *context) {
  APP_LOG(APP_LOG_LEVEL_DEBUG, "App Message Failed to Send!");
}



static void select_click_handler(ClickRecognizerRef recognizer, void *context) {
  text = "Loading";
	scroll_text_reload();
	dictation_session_start(s_dictation_session);
}

void config_provider(void *context) {
	// single click
	window_single_click_subscribe(BUTTON_ID_SELECT, (ClickHandler)select_click_handler);
}

void scroll_text_reload(){
	window_stack_pop(false);
	scroll_text_init(text);
	scroll_text_show(false);
}


void scroll_text_show(bool animate){
	window_stack_push(window, animate);
}

void scroll_text_init(char* text_){
	text = text_;

	
	window = window_create();
	Layer *rootLayer = window_get_root_layer(window);
	GRect bounds = layer_get_bounds(rootLayer);
	
	
	scrollL = scroll_layer_create(bounds);
	
	GTextAttributes *s_attributes = graphics_text_attributes_create();
  graphics_text_attributes_enable_screen_text_flow(s_attributes, PBL_IF_ROUND_ELSE(7,0));
	
	
	textL = text_layer_create(GRect(paddingX, paddingY, bounds.size.w - (paddingX*2), maxH));
	text_layer_set_text(textL, text_);
	text_layer_set_font(textL, fonts_get_system_font(FONT_KEY_DROID_SERIF_28_BOLD));
	text_layer_set_background_color(textL, GColorClear);
	text_layer_set_text_alignment(textL, GTextAlignmentCenter);
	scroll_layer_add_child(scrollL, text_layer_get_layer(textL));
	
	GSize max_size = text_layer_get_content_size(textL);
	
	scroll_layer_set_content_size(scrollL, GSize(bounds.size.w, max_size.h + (paddingY * 3)));
	//scroll_layer_set_shadow_hidden(scrollL, false);
	scroll_layer_set_click_config_onto_window(scrollL, window);
	
	layer_add_child(rootLayer, scroll_layer_get_layer(scrollL));
		
	#if defined(PBL_ROUND)
		text_layer_enable_screen_text_flow_and_paging(textL, 2);
		scroll_layer_set_paging(scrollL, true);
	#endif
	
	cbacks.click_config_provider = &config_provider;
	scroll_layer_set_callbacks(scrollL, cbacks);
}

void scroll_text_destroy(){
	window_destroy(window);
	scroll_layer_destroy(scrollL);
	text_layer_destroy(textL);
}








static void dictation_session_callback(DictationSession *session, DictationSessionStatus status, char *transcription, void *context) {
  // Print the results of a transcription attempt
  APP_LOG(APP_LOG_LEVEL_INFO, "Dictation status: %d", (int)status);
	if(status == DictationSessionStatusSuccess) {
		// Display the dictated text
		strcpy(s_last_text, transcription);
		
		DictionaryIterator *iter;
		app_message_outbox_begin(&iter);

		dict_write_cstring(iter, STRING, s_last_text);

		//dict_write_end(iter);
		app_message_outbox_send();
		
		//text_layer_set_text(s_output_layer, s_last_text);
	}else{
		vibes_double_pulse();
		dictation_session_start(s_dictation_session);
	}
}

void init(){
	app_message_register_inbox_received(in_received_handler);
  app_message_register_inbox_dropped(in_dropped_handler);
  app_message_register_outbox_failed(out_failed_handler);
	
	app_message_open(app_message_inbox_size_maximum(), app_message_outbox_size_maximum());
	
	scroll_text_init("Loading");
	scroll_text_show(0);
	s_dictation_session = dictation_session_create(sizeof(s_last_text),dictation_session_callback, NULL);
	dictation_session_start(s_dictation_session);
}

void deinit(){
	
}

int main(){
	init();
	app_event_loop();
	deinit();
}