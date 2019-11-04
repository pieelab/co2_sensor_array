    # > rsconnect::deployApp('~/repos/co2_sensor_array/shiny/co2_sensors/')

library(shiny)
library(dplyr)
library(data.table)
library(ggplot2)
library(lubridate)
# library(plotly)
library(RMariaDB)
library(Cairo)
library(R.utils)
library(shinyWidgets)

tzone = 'America/Vancouver'
Sys.setenv(TZ=tzone)

ranges_dt <- fread("ranges.csv") 

production_local_con <- function(){
    con <- DBI::dbConnect(RMariaDB::MariaDB(),
                          host = "localhost",
                          user = "rshiny",
                          password = "rshiny",
                          dbname = "co2_sensors"
    )
}

dev_con <- function(){
    source('./.con_to_remote.R')
    con <- DBI::dbConnect(RMariaDB::MariaDB(),
                          host = host,
                          user = "co2_reader",
                          password = password,
                          dbname = "co2_sensors"
    )
    
}

date_ranger <-function(date_range){
    
    t <- Sys.time()
    local_t <- sprintf("%02d:%02d:%02d",hour(t),minute(t),round(second(t)))
    local_tz_datetime <- lubridate::ymd_hms(paste(date_range, local_t), tz=Sys.timezone())    
    select_datetime_range <- with_tz(local_tz_datetime, "UTC")

    return(select_datetime_range)
}
get_co2_data <- function(select_datetime_range){
    if(System$getHostname()== 'linode')
        con <- production_local_con()
    else
        con <- dev_con()
    
    d1 <- select_datetime_range[1]
    d2 <- select_datetime_range[2]
    
    tables <- RMariaDB::dbListTables(con)
    select_tables <- function(con,name){
        tb <- RMariaDB::dbGetQuery(con, sprintf("SELECT * FROM %s WHERE T BETWEEN '%s' AND '%s'", name, d1, d2))
        out <- as.data.table(tb)
        out[,device_id := name]
        out[,CO2_ppm := PPM_10X/10]
        out[,sensor_id := as.numeric(SENSOR)]
        
    }
    dt <- rbindlist(lapply(tables, select_tables, con=con))
    
    dt <- ranges_dt[dt, on='sensor_id']
    dt[, in_range := between(CO2_ppm,min,max), by=sensor_id]
    DBI::dbDisconnect(con) 
    dt 
}

# Define UI for application that draws a histogram
ui <- fluidPage(
    setBackgroundColor("ghostwhite"),
    # Application title
    titlePanel("CO2 sensors"),
    sidebarPanel(
        dateRangeInput("dates", "Date range", start = Sys.Date() - 2, end = Sys.Date(), min = NULL,
                       max = Sys.Date(), format = "yyyy-mm-dd", startview = "month", weekstart = 0,
                       language = "en", separator = " to ", width = NULL),
        
       h4(htmlOutput( "last_updated"))
    ),
    
    
    mainPanel(
        
        # Output: Tabset w/ plot, summary, and table ----
        tabsetPanel(type = "tabs",
                    tabPanel("Plot",
                             
                            plotOutput("zoom_view", 
                                               height="600px",
                                               width='800px', ),
                            plotOutput("overall_view", 
                                       height="100px",
                                       width='800px',
                                       dblclick = "overview_dblclick",
                                       brush = brushOpts(
                                           id = "overview_brush",
                                           resetOnNew = FALSE, direction='x'))
                            ),
                    tabPanel("Summary",  tableOutput("table")),
                    tabPanel("Warnings", verbatimTextOutput("TODO")),
                    tabPanel("Download", downloadButton("downloadData", "Download"))
        )
        
    )
    
    
)

# Define server logic required to draw a histogram
server <- function(input, output, session) {
    range_zoom <- reactiveValues(x = NULL, y = NULL)
    
    autoInvalidate <- reactiveTimer(60000, session)
    data_input <- reactive({
        autoInvalidate()
        print("updating data")
        date_range <- date_ranger(input$dates)
        date_range[2] <- date_range[2] + 3600
        dt <- get_co2_data(date_range)
        
        list(dt=dt,date_range=date_range, updated_time=with_tz(Sys.time(),tzone))
    })
    output$last_updated <- renderText({
        d <- data_input()
        HTML(
            sprintf("<b>Plot updated at %s</b>", 
                as.character(d$updated_time))
        )
    })
    output$overall_view <- renderPlot(execOnResize = FALSE,bg="transparent",{
        d <- data_input()
        device_sensor_map <- unique(d$dt, by=c("sensor_id", "device_id"))[,c("sensor_id", "device_id")]
        device_sensor_map[, `:=`(x=d$date_range[1],y=900, CO2_ppm=0)]
        dd <- data.table(x =d$updated_time , y = +Inf, xend =d$updated_time , yend = 400)

        pl <- ggplot(d$dt,  aes(T,CO2_ppm)) +
            geom_line(aes( group=sensor_id), colour="black", size=.5, alpha=.5) +
            scale_y_continuous(name=NULL, labels=NULL) +
            scale_x_datetime(name="", limits = with_tz(d$date_range, tzone), timezone = tzone, 
                             breaks = scales::pretty_breaks(n = 12)) +
            theme_minimal() + theme(legend.position = 'none', panel.spacing = unit(.5, "line"),
                  panel.background = element_rect(fill='white', colour='black',
                                                  size = 0.5, linetype = "solid"),
                  strip.background =element_rect(fill="grey"),
                  strip.text = element_text(colour = 'black',size = 12))+
            geom_segment(data=dd,
                         aes(x=x,y=y,yend=yend, xend=xend),
                         colour='blue', size=1,
                         arrow = arrow(length = unit(0.5, "cm")))
        
        # ggplotly(pl,dynamicTicks =FALSE ) %>%
        # # rangeslider() %>%
        # layout(legend = list(orientation = "h", x = 0.4, y = 1.1), selectdirection='h')
        pl
    })
    
    output$zoom_view <- renderPlot(execOnResize = FALSE,bg="transparent", {
        # generate bins based on input$bins from ui.R
        # theme_set(c + )
        
        d <- data_input()
        device_sensor_map <- unique(d$dt, by=c("sensor_id", "device_id"))[,c("sensor_id", "device_id")]
        # device_sensor_map[, `:=`(x= ifelse(is.null(range_zoom$x), d$date_range[1],range_zoom$x[1]),
        #                          y=900, CO2_ppm=0)]
        if(!is.null(range_zoom$x)){
            device_sensor_map[, x:=range_zoom$x[1]]
        }
        else{
            device_sensor_map[, x:=d$date_range[1]]
        }
        
        device_sensor_map[, `:=`(ax =d$updated_time , ay = +Inf,  ayend = 400)]
        
        pl <- ggplot(d$dt[T %between% range_zoom$x],  aes(T,CO2_ppm)) +
            geom_hline(data=ranges_dt, mapping = aes(yintercept=set), colour="grey", linetype=2)+
            geom_line(colour="black", size=.5, alpha=.5) +
            geom_point(mapping=aes(colour=in_range), size=1) +
            facet_grid(sensor_id  ~ .) +
            geom_label(data=device_sensor_map, aes(label=device_id, x=x), y=-Inf, vjust=-.1, colour="blue",hjust=0)+
            scale_y_continuous(name="[CO2] (PPM)") +
            scale_x_datetime(name="", limits = with_tz(d$date_range, tzone), timezone = tzone, 
                             breaks = scales::pretty_breaks(n = 12)) +
            coord_cartesian(xlim = range_zoom$x, expand = FALSE)+
            scale_colour_manual(values = c("red", "black")) +
            theme_minimal() + theme(legend.position = 'none', panel.spacing = unit(.5, "line"),
                                    panel.background = element_rect(fill='white', colour='black',
                                                                    size = 0.5, linetype = "solid"),
                                    strip.background =element_rect(fill="grey"),
                                    strip.text = element_text(colour = 'black',size = 12))+
            geom_segment(data=device_sensor_map,
                         aes(x=ax,y=ay,yend=ayend, xend=ax),
                         colour='blue', size=.5,
                         arrow = arrow(length = unit(0.5, "cm")))
        
            
        
        pl
    })
    output$dateText  <- renderText({
        paste("input$date is", as.character(input$dates))
    })
    
    output$table <- renderTable({
        d <- data_input()
        d$dt[,.(min=min(CO2_ppm),
                max=max(CO2_ppm),
                mean=mean(CO2_ppm),
                sd=sd(CO2_ppm),
                median=median(CO2_ppm),
                last_point = sprintf("%s ago", as.character(hms::round_hms(hms::as_hms(Sys.time() - T[.N]), 1))),
                N=.N,
                avg_sampling_period = mean(diff(T))
                ),by="device_id,sensor_id"]
        
    })
    output$downloadData <- downloadHandler(
        filename = function() {
            r <- data_input()$date_range
            r <- stringr::str_replace_all(r, '\ |:', '-')
            sprintf("co2_sensors_%s_%s.csv", r[1], r[2])
        },
        content = function(file) {
            fwrite(data_input()$dt, file, row.names = FALSE)
        }
    )
    observe({
        brush <- input$overview_brush
        if (!is.null(brush)) {
            range_zoom$y <- c(brush$ymin, brush$ymax)
            range_zoom$x <- as.POSIXct(c(brush$xmin, brush$xmax), origin='1970-01-01')
            
            
        } else {
            range_zoom$x <- data_input()$date_range
            range_zoom$y <- NULL
        }
    })
    
}

# Run the application 
shinyApp(ui = ui, server = server)
